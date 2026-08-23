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
# DARK GLASS THEME — warm amber accent, floating glow orbs,
# terminal-style panels (reference: WorkForge landing style)
# =========================================================
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&display=swap');

    .stApp {
        background:
            radial-gradient(circle at 12% 18%, rgba(217,119,6,0.16), transparent 24%),
            radial-gradient(circle at 88% 12%, rgba(180,83,9,0.13), transparent 28%),
            radial-gradient(circle at 78% 68%, rgba(217,119,6,0.10), transparent 32%),
            radial-gradient(circle at 18% 82%, rgba(120,53,15,0.13), transparent 30%),
            radial-gradient(circle at 50% 45%, rgba(0,0,0,0), transparent 40%),
            linear-gradient(180deg, #0a0908 0%, #0d0c0a 100%);
        color: #e7e5e4;
    }
    section[data-testid="stSidebar"] {
        background: rgba(20, 18, 16, 0.55);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border-right: 1px solid rgba(251, 146, 60, 0.12);
    }
    section[data-testid="stSidebar"] * { color: #d6d3d1; }

    /* Glass panel */
    .glass-card {
        background: rgba(255, 255, 255, 0.035);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.09);
        border-radius: 18px;
        padding: 20px 22px;
        margin-bottom: 14px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.35);
    }

    /* Eyebrow label + title, matching the reference's "TRY TO BREAK IT" style */
    .eyebrow {
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 3px;
        color: #fb923c;
        text-transform: uppercase;
        margin-bottom: 8px;
    }
    .main-title {
        font-size: 40px;
        font-weight: 800;
        color: #fafaf9;
        line-height: 1.15;
        margin-bottom: 10px;
        letter-spacing: -0.5px;
    }
    .main-title .accent { color: #fb923c; }
    .subtitle { color: rgba(231,229,228,0.6); font-size: 15px; margin-bottom: 24px; max-width: 640px; }

    /* Terminal-style card (mac-style dots) for progress / query panels */
    .terminal-card {
        background: rgba(12, 10, 9, 0.65);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255,255,255,0.09);
        border-radius: 16px;
        padding: 0;
        margin-bottom: 14px;
        overflow: hidden;
        box-shadow: 0 8px 32px rgba(0,0,0,0.35);
    }
    .terminal-header {
        display: flex; gap: 7px; align-items: center;
        padding: 12px 16px;
        border-bottom: 1px solid rgba(255,255,255,0.06);
        background: rgba(255,255,255,0.02);
    }
    .terminal-dot { width: 11px; height: 11px; border-radius: 50%; }
    .terminal-dot.red { background: #f87171; }
    .terminal-dot.amber { background: #fbbf24; }
    .terminal-dot.tan { background: #d6a678; }
    .terminal-body {
        padding: 16px 18px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 13px;
    }

    .metric-card {
        background: rgba(255,255,255,0.035);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255,255,255,0.09);
        border-radius: 14px;
        padding: 14px;
        text-align: center;
    }
    .metric-value { font-size: 24px; font-weight: 800; color: #fb923c; }
    .metric-label { color: rgba(231,229,228,0.55); font-size: 12px; margin-top: 2px; }

    .job-card {
        background: rgba(255,255,255,0.03);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border: 1px solid rgba(255,255,255,0.09);
        border-left: 3px solid #fb923c;
        border-radius: 16px;
        padding: 18px 20px;
        margin-bottom: 14px;
        transition: border-color 0.2s ease;
    }
    .job-card:hover { border-color: rgba(255,255,255,0.18); }
    .job-title { font-size: 18px; font-weight: 700; color: #fafaf9; }
    .job-company { color: #fdba74; font-size: 13px; margin-top: 3px; font-weight: 600; }
    .job-description { color: rgba(231,229,228,0.7); line-height: 1.55; margin-top: 8px; font-size: 13px; }

    .badge {
        display: inline-block; padding: 3px 10px; border-radius: 20px;
        font-size: 11px; font-weight: 700; margin: 2px;
        border: 1px solid rgba(255,255,255,0.14);
        background: rgba(255,255,255,0.05);
        color: #e7e5e4;
    }
    .badge-match-high { background: rgba(34,197,94,0.14); color: #4ade80; border-color: rgba(74,222,128,0.35); }
    .badge-match-mid { background: rgba(251,191,36,0.14); color: #fbbf24; border-color: rgba(251,191,36,0.35); }
    .badge-match-low { background: rgba(168,162,158,0.14); color: #d6d3d1; border-color: rgba(168,162,158,0.35); }
    .badge-source { background: rgba(251,146,60,0.14); color: #fdba74; border-color: rgba(251,146,60,0.35); }

    .progress-row { font-size: 14px; padding: 4px 0; color: rgba(231,229,228,0.85); font-family: 'JetBrains Mono', monospace; }

    /* Streamlit primary button -> warm pill button, matches "Get started" */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(90deg, #f59e0b, #fb923c);
        color: #1c1917;
        border: none;
        border-radius: 999px;
        font-weight: 700;
        box-shadow: 0 4px 20px rgba(251,146,60,0.25);
    }
    div.stButton > button[kind="primary"]:hover {
        box-shadow: 0 6px 26px rgba(251,146,60,0.4);
        transform: translateY(-1px);
    }
    div.stButton > button[kind="secondary"] {
        background: rgba(255,255,255,0.04);
        color: #e7e5e4;
        border: 1px solid rgba(255,255,255,0.12);
        border-radius: 999px;
    }

    /* File uploader + inputs: subtle glass */
    div[data-testid="stFileUploaderDropzone"] {
        background: rgba(255,255,255,0.03);
        border: 1px dashed rgba(251,146,60,0.35);
        border-radius: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# HEADER
# =========================================================
st.markdown('<div class="eyebrow">Resume → Ranked Jobs</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="main-title">Skip the noise. <span class="accent">Get jobs that fit.</span></div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="subtitle">One LLM call reads your resume. Everything after that — search, '
    'scraping, date filtering, deduping, and ranking — is deterministic Python.</div>',
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
    min_match_percent = st.slider(
        "Minimum Match %",
        min_value=0, max_value=80, value=20, step=5,
        help="Jobs scoring below this relevance % are dropped — prevents "
             "an unrelated job (e.g. 0% match) from showing up just "
             "because it happened to fall inside the date range.",
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
    placeholder.markdown(
        '<div class="terminal-card">'
        '<div class="terminal-header">'
        '<div class="terminal-dot red"></div>'
        '<div class="terminal-dot amber"></div>'
        '<div class="terminal-dot tan"></div>'
        '</div>'
        f'<div class="terminal-body">{"".join(lines)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )


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
            min_match_percent=min_match_percent,
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
    c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
    c1.markdown(f'<div class="metric-card"><div class="metric-value">{len(jobs)}</div><div class="metric-label">Final Jobs</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card"><div class="metric-value">{stats.get("unique_companies", 0)}</div><div class="metric-label">Companies</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card"><div class="metric-value">{stats.get("average_match", 0)}%</div><div class="metric-label">Avg Match</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="metric-card"><div class="metric-value">{stats.get("removed_duplicates", 0)}</div><div class="metric-label">Duplicates</div></div>', unsafe_allow_html=True)
    c5.markdown(f'<div class="metric-card"><div class="metric-value">{stats.get("excluded_undated", 0)}</div><div class="metric-label">No Verifiable Date</div></div>', unsafe_allow_html=True)
    c6.markdown(f'<div class="metric-card"><div class="metric-value">{stats.get("excluded_out_of_range", 0)}</div><div class="metric-label">Date Out of Range</div></div>', unsafe_allow_html=True)
    c7.markdown(f'<div class="metric-card"><div class="metric-value">{stats.get("removed_low_relevance", 0)}</div><div class="metric-label">Low Relevance</div></div>', unsafe_allow_html=True)

    st.divider()
    st.subheader(f"🎯 Final Job Table ({len(jobs)})")

    if not jobs:
        hints = []
        if stats.get("excluded_undated", 0) > stats.get("excluded_out_of_range", 0):
            hints.append(
                "most results had no verifiable posting date (many job boards "
                "block scraping) — try checking **'Include jobs with unknown/"
                "unverifiable dates'**, or pick a wider freshness window"
            )
        if stats.get("removed_low_relevance", 0) > 0:
            hints.append("some jobs were filtered for low relevance — try lowering **Minimum Match %**")
        if stats.get("excluded_out_of_range", 0) > 0:
            hints.append("some jobs had dates outside your selected range — try **Last 7 days** or **Any time**")
        hint_text = "; ".join(hints) if hints else (
            "try widening the date range, clearing the location filter, or "
            "increasing Search Results per Query"
        )
        st.error(f"No jobs matched your filters — {hint_text}.")
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
