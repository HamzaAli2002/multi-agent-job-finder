import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

from src.pipeline import run_pipeline

# =========================================================
# PAGE CONFIG
# =========================================================
st.set_page_config(
    page_title="Job Finder — Resume to Ranked Jobs",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================================================
# TRANSPARENT / GLASS THEME
# =========================================================
st.markdown(
    """
    <style>
    .stApp {
        background: linear-gradient(135deg, #0b1220 0%, #111827 45%, #0b1220 100%);
        color: #e5e7eb;
    }
    section[data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(10px);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }
    .glass-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.10);
        border-radius: 16px;
        padding: 18px 20px;
        margin-bottom: 14px;
    }
    .main-title {
        font-size: 34px;
        font-weight: 800;
        background: linear-gradient(90deg, #38bdf8, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2px;
    }
    .subtitle { color: rgba(229,231,235,0.65); font-size: 14px; margin-bottom: 20px; }

    .metric-card {
        background: rgba(255,255,255,0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 14px;
        padding: 14px;
        text-align: center;
    }
    .metric-value { font-size: 24px; font-weight: 800; color: #38bdf8; }
    .metric-label { color: rgba(229,231,235,0.6); font-size: 12px; }

    .job-card {
        background: rgba(255,255,255,0.045);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.10);
        border-left: 3px solid #38bdf8;
        border-radius: 14px;
        padding: 18px 20px;
        margin-bottom: 14px;
    }
    .job-title { font-size: 18px; font-weight: 700; color: #f8fafc; }
    .job-company { color: #7dd3fc; font-size: 13px; margin-top: 3px; font-weight: 600; }
    .job-description { color: rgba(229,231,235,0.75); line-height: 1.55; margin-top: 8px; font-size: 13px; }

    .badge {
        display: inline-block; padding: 3px 10px; border-radius: 20px;
        font-size: 11px; font-weight: 700; margin: 2px;
        border: 1px solid rgba(255,255,255,0.15);
        background: rgba(255,255,255,0.06);
        color: #e5e7eb;
    }
    .badge-match-high { background: rgba(34,197,94,0.15); color: #4ade80; border-color: rgba(74,222,128,0.4); }
    .badge-match-mid { background: rgba(250,204,21,0.15); color: #facc15; border-color: rgba(250,204,21,0.4); }
    .badge-match-low { background: rgba(148,163,184,0.15); color: #cbd5e1; border-color: rgba(148,163,184,0.4); }
    .badge-source { background: rgba(167,139,250,0.15); color: #c4b5fd; border-color: rgba(167,139,250,0.4); }

    .progress-row { font-size: 14px; padding: 3px 0; color: rgba(229,231,235,0.85); }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# HEADER
# =========================================================
st.markdown('<div class="main-title">🧭 Job Finder</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Resume → Python-powered search, date-range filtering, '
    'and relevance ranking. One LLM call for analysis — everything else is algorithmic.</div>',
    unsafe_allow_html=True,
)

# =========================================================
# SIDEBAR — SEARCH SETTINGS (BRD Section 14)
# =========================================================
with st.sidebar:
    st.header("⚙️ Search Settings")

    max_search_results = st.slider("Search Results per Query", min_value=3, max_value=15, value=5, step=1)
    max_jobs = st.slider("Maximum Jobs (final list)", min_value=3, max_value=30, value=10, step=1)

    st.divider()
    st.subheader("📅 Freshness / Posting Date")
    freshness = st.radio(
        "Show jobs posted:",
        ["Last 24 hours", "Last 3 days", "Last 7 days", "Custom range", "Any time"],
        index=1,  # default: Last 3 days
    )

    if freshness == "Custom range":
        col_a, col_b = st.columns(2)
        with col_a:
            from_date_input = st.date_input("From Date", value=date.today().replace(day=1))
        with col_b:
            to_date_input = st.date_input("To Date", value=date.today())
    elif freshness == "Any time":
        from_date_input = None
        to_date_input = None
    else:
        days_map = {"Last 24 hours": 1, "Last 3 days": 3, "Last 7 days": 7}
        from_date_input = date.today() - timedelta(days=days_map[freshness])
        to_date_input = date.today()

    include_undated = st.checkbox(
        "Include jobs with unknown/unverifiable dates", value=(freshness == "Any time")
    )

    st.divider()
    st.subheader("📍 Filters")
    location_filter = st.text_input("Location contains", placeholder="e.g. Karachi, Remote")
    employment_type_filter = st.selectbox(
        "Employment Type", ["Any", "Full-time", "Part-time", "Contract", "Internship", "Remote", "Hybrid", "On-site"]
    )

    st.divider()
    st.caption(
        "Minimum LLM usage: only the resume analysis stage calls Gemini. "
        "Search, scraping, date filtering, dedup, and ranking are pure Python."
    )

# =========================================================
# UPLOAD + RUN
# =========================================================
uploaded_file = st.file_uploader("📄 Upload Resume (PDF / DOCX)", type=["pdf", "docx"])
start_search = st.button("🚀 Find Matching Jobs", type="primary", use_container_width=True)

# =========================================================
# PROGRESS UI (BRD Section 15)
# =========================================================
STAGE_LABELS = {
    "resume_extracted": "Resume uploaded & text extracted",
    "profile_analyzed": "Candidate profile analyzed",
    "queries_generated": "Search queries generated",
    "jobs_searched": "Searching jobs",
    "jobs_scraped": "Scraping job pages",
    "date_filtered": "Applying date filter",
    "jobs_processed": "Filtering, deduplicating & ranking results",
    "results_ready": "Final results ready",
}
STAGE_ORDER = list(STAGE_LABELS.keys())


def render_progress(placeholder, states: dict):
    lines = []
    for key in STAGE_ORDER:
        status = states.get(key, "pending")
        icon = {"pending": "⬜", "running": "🔄", "done": "✅", "error": "❌"}[status]
        lines.append(f'<div class="progress-row">{icon} {STAGE_LABELS[key]}</div>')
    placeholder.markdown('<div class="glass-card">' + "".join(lines) + "</div>", unsafe_allow_html=True)


if start_search:
    if uploaded_file is None:
        st.warning("⚠️ Please upload a resume first.")
        st.stop()

    suffix = Path(uploaded_file.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        resume_path = tmp.name

    st.divider()
    st.subheader("⚡ Pipeline Progress")
    progress_placeholder = st.empty()
    stage_states: dict[str, str] = {}
    render_progress(progress_placeholder, stage_states)

    def on_progress(stage_key: str, status: str):
        stage_states[stage_key] = status
        render_progress(progress_placeholder, stage_states)

    # from_dt = start of day, to_dt = end of day, so "today" is fully inclusive.
    from_dt = datetime.combine(from_date_input, datetime.min.time()) if from_date_input else None
    to_dt = datetime.combine(to_date_input, datetime.max.time()) if to_date_input else None

    try:
        result = run_pipeline(
            resume_path=resume_path,
            max_jobs=max_jobs,
            max_search_results=max_search_results,
            from_date=from_dt,
            to_date=to_dt,
            location_filter=location_filter,
            employment_type_filter=employment_type_filter,
            include_undated=include_undated,
            progress=on_progress,
        )
        st.session_state["pipeline_result"] = result
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.exception(e)
    finally:
        if os.path.exists(resume_path):
            os.remove(resume_path)

# =========================================================
# CANDIDATE PROFILE + RESULTS
# =========================================================
if "pipeline_result" in st.session_state:
    res = st.session_state["pipeline_result"]
    cand = res.get("candidate", {})
    jobs = res.get("jobs", [])
    stats = res.get("statistics", {})
    queries = res.get("queries", [])

    st.divider()
    st.subheader("🧑‍💻 Candidate Profile")
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Target Role", cand.get("role", "—"))
    c2.metric("Experience", cand.get("experience_level", "—"))
    c3.metric("Location", cand.get("location", "—"))
    c4.metric("Employment Type", cand.get("employment_type", "—"))
    st.markdown("**Extracted Skills:**")
    st.markdown(
        "".join([f'<span class="badge">{s}</span>' for s in cand.get("skills", [])]),
        unsafe_allow_html=True,
    )
    with st.expander("🔍 Optimized search queries used"):
        for q in queries:
            st.write(f"• {q}")
    st.markdown("</div>", unsafe_allow_html=True)

    st.subheader("📊 Match Insights")
    st.caption(
        f"Search freshness bias sent to Tavily: **{stats.get('search_time_range', 'none')}**  |  "
        f"Search results found: {stats.get('search_results_found', 0)}  |  "
        f"Pages scraped: {stats.get('raw_jobs_scraped', 0)}  |  "
        f"Non-job pages removed: {stats.get('removed_non_job', 0)}"
    )
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.markdown(f'<div class="metric-card"><div class="metric-value">{len(jobs)}</div><div class="metric-label">Final Jobs</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card"><div class="metric-value">{stats.get("unique_companies", 0)}</div><div class="metric-label">Companies</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card"><div class="metric-value">{stats.get("average_match", 0)}%</div><div class="metric-label">Avg Match</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="metric-card"><div class="metric-value">{stats.get("removed_duplicates", 0)}</div><div class="metric-label">Duplicates Removed</div></div>', unsafe_allow_html=True)
    c5.markdown(f'<div class="metric-card"><div class="metric-value">{stats.get("excluded_by_date", 0)}</div><div class="metric-label">Outside Date Range</div></div>', unsafe_allow_html=True)

    st.divider()
    st.subheader(f"🎯 Final Job Table ({len(jobs)})")

    if not jobs:
        st.error(
            "No jobs matched your filters. Try widening the date range, clearing the "
            "location filter, or increasing Search Results per Query."
        )
    else:
        table_rows = [{
            "Job": j.get("title"),
            "Company": j.get("company"),
            "Date": j.get("posting_date"),
            "Location": j.get("location"),
            "Match": f'{j.get("match_percent", 0)}%',
            "Link": j.get("url"),
        } for j in jobs]
        df = pd.DataFrame(table_rows)
        st.dataframe(
            df,
            use_container_width=True,
            column_config={"Link": st.column_config.LinkColumn("Link", display_text="Open")},
            hide_index=True,
        )
        st.download_button("📥 Download Results CSV", df.to_csv(index=False), "jobs.csv", "text/csv")

        st.write("")
        st.subheader("📋 Job Cards")
        for idx, job in enumerate(jobs, 1):
            match = job.get("match_percent", 0)
            match_class = "badge-match-high" if match >= 60 else ("badge-match-mid" if match >= 35 else "badge-match-low")
            st.markdown(
                f"""
                <div class="job-card">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <div class="job-title">{idx}. {job.get('title', 'Job Opening')}</div>
                            <div class="job-company">🏢 {job.get('company', 'Company')} &nbsp;•&nbsp; 📍 {job.get('location', 'Location')}</div>
                        </div>
                        <div>
                            <span class="badge {match_class}">{match}% match</span>
                            <span class="badge">{job.get('employment_type', 'Full-time')}</span>
                        </div>
                    </div>
                    <div style="margin-top: 8px; color: rgba(229,231,235,0.55); font-size: 12px;">
                        📅 <b>Posted:</b> {job.get('posting_date', 'date not available')}
                        &nbsp;•&nbsp; <span class="badge badge-source">{job.get('extraction_method', '')}</span>
                    </div>
                    <div class="job-description">{job.get('description', 'Job opportunity matched from web search.')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if job.get("url"):
                st.link_button("🔗 Apply Now ↗", job["url"])
            st.write("")

    if st.button("🗑️ Clear & Restart"):
        del st.session_state["pipeline_result"]
        st.rerun()
