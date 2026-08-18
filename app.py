import json
import os
import re
import tempfile
from pathlib import Path
import pandas as pd
import streamlit as st

# --- Pipeline Components Import ---
from src.tools.resume_reader import read_resume
from src.chains.analyzer import analyzer_chain
from src.agents.job_search_agent import job_search_agent
from src.agents.job_scraper_agent import job_scraper_agent
from src.processors.job_result_processor import process_jobs, get_job_statistics

# =========================================================
# PAGE CONFIG & STYLING
# =========================================================
st.set_page_config(
    page_title="Resume → AI Job Matcher",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .stApp { background: #0f172a; color: #f8fafc; }
    .main-title { font-size: 36px; font-weight: 800; margin-bottom: 5px; color: #f8fafc; }
    .subtitle { font-size: 15px; color: #94a3b8; margin-bottom: 25px; }
    .metric-card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 15px; text-align: center; }
    .metric-value { font-size: 26px; font-weight: 800; color: #38bdf8; }
    .metric-label { color: #94a3b8; font-size: 13px; }
    .job-card { background: #1e293b; border: 1px solid #334155; border-radius: 14px; padding: 20px; margin-bottom: 15px; }
    .job-title { font-size: 19px; font-weight: 700; color: #f1f5f9; }
    .job-company { color: #60a5fa; font-size: 14px; margin-top: 4px; font-weight: 600; }
    .job-description { color: #cbd5e1; line-height: 1.6; margin-top: 10px; font-size: 14px; }
    .badge { display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 600; margin: 3px; }
    .badge-blue { background: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6; }
    .badge-cyan { background: #164e63; color: #67e8f9; border: 1px solid #06b6d4; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# SMART EXTRACTORS & PARSERS
# =========================================================
def _extract_agent_content(agent_result: dict) -> str:
    """LangGraph / LangChain ke har format se text nikalta hy."""
    if not isinstance(agent_result, dict):
        return str(agent_result)

    messages = agent_result.get("messages", [])
    if not messages:
        return str(agent_result)

    # 1. Piche se check karein ke kis AIMessage me actual content hy
    for msg in reversed(messages):
        content = getattr(msg, "content", None)
        if content is None and isinstance(msg, dict):
            content = msg.get("content", "")

        # Agar content list format me ho (Gemini / Anthropic style)
        if isinstance(content, list):
            parts = []
            for p in content:
                if isinstance(p, str):
                    parts.append(p)
                elif isinstance(p, dict) and "text" in p:
                    parts.append(p["text"])
            content = "\n".join(parts)

        if isinstance(content, str) and content.strip():
            return content.strip()

    # 2. Agar AIMessage me na ho to Tool outputs collect karein
    tool_texts = []
    for msg in messages:
        c = getattr(msg, "content", "")
        if c and isinstance(c, str) and len(c) > 20:
            tool_texts.append(c)
    
    if tool_texts:
        return "\n\n".join(tool_texts)

    return str(messages[-1])


def _parse_scraped_jobs(content: Any) -> list[dict]:
    """JSON parse karne ka robust tarika."""
    if isinstance(content, list):
        if all(isinstance(i, dict) for i in content):
            return content
        content = "\n".join([i.get("text", "") for i in content if isinstance(i, dict) and "text" in i])

    if not isinstance(content, str):
        content = str(content)

    content = content.strip()

    # Markdown blocks remove
    if "```" in content:
        content = re.sub(r"```(?:json)?", "", content).replace("```", "").strip()

    # Direct JSON try
    try:
        data = json.loads(content)
        if isinstance(data, list):
            return data
    except Exception:
        pass

    # Regex try for [ { ... } ]
    try:
        match = re.search(r"(\[\s*\{.*?\}\s*\])", content, re.DOTALL)
        if match:
            data = json.loads(match.group(1))
            if isinstance(data, list):
                return data
    except Exception:
        pass

    return []


def _fallback_extract_jobs_from_search(search_text: str, default_role: str) -> list[dict]:
    """
    Agar Scraper fail ho jaye, to Tavily ke search results se direct 
    URLs aur Job Titles extract karega taake 0 jobs na ayen.
    """
    jobs = []
    # Markdown links find karein: [Title](url)
    md_links = re.findall(r"\[(.*?)\]\((https?://[^\s\)]+)\)", search_text)
    
    for title, url in md_links:
        if any(bad in url.lower() for bad in ["google.com/search", "youtube.com", "facebook.com", "wikipedia.org"]):
            continue
        jobs.append({
            "title": title.strip() if len(title) > 3 else default_role,
            "company": "Found via Search",
            "location": "See Job Link",
            "employment_type": "Full-time / Specified on site",
            "description": "Job link found via Tavily Search. Direct details available at application link.",
            "posting_date": "Recently active",
            "url": url
        })

    # Direct URLs find karein agar markdown format me na hon
    if not jobs:
        urls = re.findall(r"(https?://[^\s\)\"'>]+)", search_text)
        for idx, url in enumerate(urls[:8], 1):
            if any(bad in url.lower() for bad in ["google.com", "tavily.com"]): continue
            jobs.append({
                "title": f"{default_role} Opening #{idx}",
                "company": "Company Career Page",
                "location": "Refer to Link",
                "employment_type": "Full-time",
                "description": "Extracted from search opening.",
                "posting_date": "Active Posting",
                "url": url
            })

    return jobs


def _safe_read_resume(tool, path: str) -> str:
    try:
        res = tool.invoke({"file_path": path}) if hasattr(tool, "invoke") else tool(path)
    except Exception:
        res = tool.invoke(path)
    if isinstance(res, str): return res
    if isinstance(res, list): return "\n".join([d.page_content if hasattr(d, "page_content") else str(d) for d in res])
    if hasattr(res, "page_content"): return res.page_content
    return str(res)


# =========================================================
# UI HEADER
# =========================================================
st.markdown('<div class="main-title">🚀 Resume → AI Job Matcher</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">AI agent pipeline with automated fallback search recovery.</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Search Settings")
    max_jobs = st.slider("Maximum Jobs", min_value=3, max_value=20, value=8, step=1)
    st.divider()

uploaded_file = st.file_uploader("📄 Upload Resume (PDF / DOCX)", type=["pdf", "docx"])
start_search = st.button("🚀 Find Matching Jobs Now", type="primary", use_container_width=True)

# =========================================================
# PIPELINE EXECUTION
# =========================================================
if start_search:
    if uploaded_file is None:
        st.warning("⚠️ Please upload a resume first.")
        st.stop()

    suffix = Path(uploaded_file.name).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getbuffer())
        resume_path = tmp.name

    st.divider()
    st.subheader("⚡ Live Pipeline Execution")

    try:
        # --- STAGE 1 ---
        with st.status("📄 **[1/5] Extracting Resume Text...**", expanded=False) as s1:
            resume_text = _safe_read_resume(read_resume, resume_path)
            st.write(f"✅ Extracted **{len(resume_text.split())} words**.")
            s1.update(label="✅ **[1/5] Resume Extracted**", state="complete")

        # --- STAGE 2 ---
        with st.status("🧠 **[2/5] Analyzing Skills & Target Roles...**", expanded=True) as s2:
            analyzer_result = analyzer_chain.invoke({"resume": resume_text})
            role = analyzer_result.get("role", "Software Engineer")
            experience_level = analyzer_result.get("experience_level", "Mid Level")
            location = analyzer_result.get("location", "Remote")
            skills = analyzer_result.get("skills", [])
            search_queries = analyzer_result.get("search_queries", [f"{role} jobs {location}"])

            c1, c2, c3 = st.columns(3)
            c1.metric("Target Role", role)
            c2.metric("Experience", experience_level)
            c3.metric("Location", location)

            st.write("**Extracted Skills:**")
            st.markdown("".join([f'<span class="badge badge-blue">{s}</span>' for s in skills[:15]]), unsafe_allow_html=True)
            s2.update(label="✅ **[2/5] Analysis Completed**", state="complete")

        # --- STAGE 3 ---
        with st.status("🔎 **[3/5] Tavily Searching Web for Jobs...**", expanded=True) as s3:
            search_input = f"""
Find 5-10 real, active job postings on the web for:
Role: {role}
Experience: {experience_level}
Location: {location}
Skills: {", ".join(skills[:6])}
Queries to try: {search_queries}

Return real job posting URLs with job titles and brief details.
"""
            search_result = job_search_agent.invoke({"messages": [{"role": "user", "content": search_input}]})
            search_content = _extract_agent_content(search_result)

            with st.expander("🔍 Click to view Tavily Search Output", expanded=False):
                st.write(search_content if search_content else "No raw text extracted.")
            s3.update(label="✅ **[3/5] Web Search Completed**", state="complete")

        # --- STAGE 4 ---
        with st.status("🕷️ **[4/5] Scraping & Structuring Job Data...**", expanded=True) as s4:
            scraper_input = f"""
Extract structured job postings from the search results below.
Search Content:
{search_content}

Return ONLY a valid JSON array of objects:
[{{"title": "Job Title", "company": "Company", "location": "Location", "employment_type": "Full-time", "description": "Brief description", "posting_date": "Recent", "url": "https://..."}}]
"""
            scraped_result = job_scraper_agent.invoke({"messages": [{"role": "user", "content": scraper_input}]})
            scraped_content = _extract_agent_content(scraped_result)
            scraped_jobs = _parse_scraped_jobs(scraped_content)

            # FALLBACK: Agar scraper fail ho jaye ya 0 de, to Search Content se extract karein
            if not scraped_jobs and search_content:
                st.info("ℹ️ Scraper agent blocked on websites. Extracting fallback jobs from search results...")
                scraped_jobs = _fallback_extract_jobs_from_search(search_content, role)

            with st.expander(f"📋 Scraper Agent Output ({len(scraped_jobs)} jobs found)", expanded=False):
                st.text(scraped_content)

            s4.update(label=f"✅ **[4/5] Scraping Completed ({len(scraped_jobs)} Jobs)**", state="complete")

        # --- STAGE 5 ---
        with st.status("⚙️ **[5/5] Processing & Filtering Results...**", expanded=False) as s5:
            final_jobs = process_jobs(scraped_jobs, max_jobs=max_jobs) if scraped_jobs else []
            # Agar process_jobs ne sab filter kar diya to direct scraped_jobs le lo
            if not final_jobs and scraped_jobs:
                final_jobs = scraped_jobs[:max_jobs]
            statistics = get_job_statistics(final_jobs) if final_jobs else {"total_jobs": len(final_jobs), "unique_companies": len(final_jobs), "jobs_with_date": 0, "jobs_without_date": len(final_jobs)}
            s5.update(label="✅ **[5/5] Pipeline Ready!**", state="complete")

        # Save to session
        st.session_state["pipeline_result"] = {
            "candidate": {"role": role, "experience_level": experience_level, "location": location, "skills": skills},
            "jobs": final_jobs,
            "statistics": statistics
        }

    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        st.exception(e)
    finally:
        if os.path.exists(resume_path):
            os.remove(resume_path)

# =========================================================
# FINAL RESULTS DISPLAY
# =========================================================
if "pipeline_result" in st.session_state:
    res = st.session_state["pipeline_result"]
    cand = res.get("candidate", {})
    jobs = res.get("jobs", [])
    stats = res.get("statistics", {})

    st.divider()
    st.subheader("📊 Match Insights")
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="metric-card"><div class="metric-value">{len(jobs)}</div><div class="metric-label">Total Jobs Found</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card"><div class="metric-value">{stats.get("unique_companies", len(jobs))}</div><div class="metric-label">Companies</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card"><div class="metric-value">{stats.get("jobs_with_date", 0)}</div><div class="metric-label">Dated</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="metric-card"><div class="metric-value">{stats.get("jobs_without_date", len(jobs))}</div><div class="metric-label">Undated</div></div>', unsafe_allow_html=True)

    st.divider()
    st.subheader(f"🎯 Matched Jobs ({len(jobs)})")

    if not jobs:
        st.error("No jobs could be extracted. Please check if Tavily Search returned valid URLs in Stage [3/5].")
    else:
        df = pd.DataFrame(jobs)
        st.download_button("📥 Download Results CSV", df.to_csv(index=False), "jobs.csv", "text/csv")
        st.write("")

        for idx, job in enumerate(jobs, 1):
            st.markdown(
                f"""
                <div class="job-card">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div>
                            <div class="job-title">{idx}. {job.get('title', 'Job Opening')}</div>
                            <div class="job-company">🏢 {job.get('company', 'Company')} &nbsp;•&nbsp; 📍 {job.get('location', 'Location')}</div>
                        </div>
                        <span class="badge badge-cyan">{job.get('employment_type', 'Full-time')}</span>
                    </div>
                    <div style="margin-top: 8px; color: #94a3b8; font-size: 13px;">📅 <b>Posted:</b> {job.get('posting_date', 'Recently Active')}</div>
                    <div class="job-description">{job.get('description', 'Job opportunity matched from web search.')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if job.get("url"):
                st.link_button(f"🔗 Apply Now ↗", job["url"])
            st.write("")

    if st.button("🗑️ Clear & Restart"):
        del st.session_state["pipeline_result"]
        st.rerun()