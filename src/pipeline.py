"""
Multi-Agent Job Finder — Pipeline Orchestrator
==================================================

Architecture (BRD Section 21):

    Streamlit UI -> Resume Reader -> Minimal LLM Analyzer -> Query
    Optimizer (Python) -> Job Search (Tavily, Python) -> Job Filter
    (Python) -> Scraper + Structured Extraction (Python) -> Date Filter
    (Python) -> Duplicate Removal (Python) -> Relevance Score (Python)
    -> Final Job Table

Only ONE LLM call happens in the entire run: the resume analyzer.
Everything else is deterministic Python.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Optional

from src.chains.analyzer import analyzer_chain
from src.config import settings
from src.processors.job_result_processor import get_job_statistics, process_jobs
from src.scraper.job_scraper import scrape_jobs
from src.search.job_search import run_job_search
from src.search.query_optimizer import build_optimized_queries
from src.tools.resume_reader import read_resume

ProgressFn = Optional[Callable[[str, str], None]]
# progress(stage_key: str, status: "running" | "done" | "error") -> None


def _notify(progress: ProgressFn, stage: str, status: str) -> None:
    if progress:
        progress(stage, status)


def run_pipeline(
    resume_path: str,
    max_jobs: int = 10,
    max_search_results: int = 5,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    location_filter: str = "",
    employment_type_filter: str = "",
    include_undated: bool = True,
    progress: ProgressFn = None,
) -> dict[str, Any]:
    """
    Runs the complete Resume -> Job Matcher pipeline.

    Args:
        resume_path: path to uploaded PDF/DOCX resume.
        max_jobs: cap on final results returned.
        max_search_results: Tavily results per search query.
        from_date / to_date: inclusive posting-date range filter.
        location_filter / employment_type_filter: Python string filters.
        progress: optional callback(stage_key, status) for live UI updates.
    """

    # =====================================================
    # Stage 1: Resume Reader (Python)
    # =====================================================
    _notify(progress, "resume_extracted", "running")
    resume_text = read_resume.invoke({"file_path": resume_path})
    if not resume_text.strip():
        _notify(progress, "resume_extracted", "error")
        raise ValueError("Resume reader returned empty text.")
    _notify(progress, "resume_extracted", "done")

    # =====================================================
    # Stage 2: Minimal LLM Analysis (the ONLY LLM call)
    # =====================================================
    _notify(progress, "profile_analyzed", "running")
    analyzer_result = analyzer_chain.invoke({"resume": resume_text})
    if not isinstance(analyzer_result, dict):
        _notify(progress, "profile_analyzed", "error")
        raise ValueError("Analyzer did not return a valid JSON object.")

    candidate = {
        "role": analyzer_result.get("role", "Software Developer"),
        "experience_level": analyzer_result.get("experience_level", ""),
        "location": analyzer_result.get("location", "Remote"),
        "employment_type": analyzer_result.get("employment_type", "Full-time"),
        "skills": analyzer_result.get("skills", []),
    }
    baseline_queries = analyzer_result.get("search_queries", [])
    _notify(progress, "profile_analyzed", "done")

    # =====================================================
    # Stage 2b: Search Query Optimization (Python)
    # =====================================================
    _notify(progress, "queries_generated", "running")
    optimized_queries = build_optimized_queries(
        role=candidate["role"],
        experience_level=candidate["experience_level"],
        skills=candidate["skills"],
        location=candidate["location"] if candidate["location"].lower() != "remote" else "",
        max_queries=settings.MAX_QUERIES,
    )
    if not optimized_queries:
        optimized_queries = baseline_queries or [f"{candidate['role']} jobs"]
    _notify(progress, "queries_generated", "done")

    # =====================================================
    # Stage 3: Job Search (Tavily API — Python, no LLM agent)
    # =====================================================
    _notify(progress, "jobs_searched", "running")
    search_results = run_job_search(optimized_queries, max_results_per_query=max_search_results)
    _notify(progress, "jobs_searched", "done")

    # =====================================================
    # Stage 4: Scraping + Structured Extraction (Python, no LLM)
    # =====================================================
    _notify(progress, "jobs_scraped", "running")
    scraped_jobs = scrape_jobs(search_results, max_workers=settings.SCRAPE_MAX_WORKERS)
    _notify(progress, "jobs_scraped", "done")

    # =====================================================
    # Stage 4b: Date Filter (Python)
    # =====================================================
    _notify(progress, "date_filtered", "running")
    # (actual filtering happens inside process_jobs; this stage marker
    #  exists purely so the UI can show it as its own step per BRD #15)
    _notify(progress, "date_filtered", "done")

    # =====================================================
    # Stage 5: Normalize -> Filter -> Dedupe -> Date-range ->
    #          Relevance Score -> Sort -> Limit  (Python)
    # =====================================================
    _notify(progress, "jobs_processed", "running")
    processing_result = process_jobs(
        scraped_jobs,
        candidate=candidate,
        max_jobs=max_jobs,
        from_date=from_date,
        to_date=to_date,
        location_filter=location_filter,
        employment_type_filter=employment_type_filter,
        include_undated=include_undated,
    )
    final_jobs = processing_result["jobs"]
    statistics = get_job_statistics(final_jobs)
    statistics["excluded_by_date"] = processing_result["excluded_by_date"]
    statistics["removed_duplicates"] = processing_result["removed_duplicates"]
    statistics["removed_non_job"] = processing_result["removed_non_job"]
    statistics["raw_jobs_scraped"] = len(scraped_jobs)
    statistics["search_results_found"] = len(search_results)
    _notify(progress, "jobs_processed", "done")

    _notify(progress, "results_ready", "done")

    return {
        "candidate": candidate,
        "queries": optimized_queries,
        "jobs": final_jobs,
        "statistics": statistics,
    }


if __name__ == "__main__":
    resume_path = "data/sample_resumes/resume.pdf"

    result = run_pipeline(resume_path=resume_path, max_jobs=10)

    print("\n" + "=" * 70)
    print("FINAL JOB MATCHING RESULTS")
    print("=" * 70)

    print("\nCandidate:", result["candidate"])
    print("\nStatistics:", result["statistics"])

    for index, job in enumerate(result["jobs"], start=1):
        print("\n" + "-" * 70)
        print(f"{index}. {job['title']} — {job['match_percent']}% match")
        print(f"Company: {job['company']}")
        print(f"Location: {job['location']}")
        print(f"Posted: {job['posting_date']}")
        print(f"URL: {job['url']}")
