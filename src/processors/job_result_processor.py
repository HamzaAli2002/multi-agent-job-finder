"""
Job Result Processor — Stage 5 (BRD Sections 5, 7, 12, 13).
Pure Python. Orchestrates:

    Normalize -> Non-job filter -> Duplicate removal -> Date-range filter
    -> Relevance scoring -> Sort (score desc, then date desc) -> Limit
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from src.processors.date_filter import filter_by_date_range, normalize_date
from src.processors.duplicate_removal import remove_duplicates
from src.processors.job_filter import filter_extracted_jobs
from src.processors.relevance_scorer import score_jobs

DATE_NOT_AVAILABLE = "date not available"


def normalize_job(job: dict) -> dict:
    """Normalize a scraped job into a consistent structure."""
    return {
        "title": str(job.get("title") or "Title not available").strip(),
        "company": str(job.get("company") or "Company not available").strip(),
        "location": str(job.get("location") or "Location not available").strip(),
        "employment_type": str(job.get("employment_type") or "Not available").strip(),
        "description": str(job.get("description") or "Description not available").strip(),
        "posting_date": str(job.get("posting_date") or DATE_NOT_AVAILABLE).strip(),
        "url": str(job.get("url") or "").strip(),
        "extraction_method": job.get("extraction_method", ""),
    }


def sort_jobs(jobs: list[dict]) -> list[dict]:
    """Sort by relevance score (desc), then by posting date (newest first)."""
    def sort_key(job: dict):
        score = job.get("relevance_score", 0)
        date = job.get("_parsed_date") or normalize_date(job.get("posting_date"))
        date_key = date.timestamp() if date else -1
        return (score, date_key)

    return sorted(jobs, key=sort_key, reverse=True)


def limit_jobs(jobs: list[dict], max_jobs: Optional[int] = None) -> list[dict]:
    if not max_jobs:
        return jobs
    return jobs[:max_jobs]


def process_jobs(
    jobs: list[dict],
    candidate: dict,
    max_jobs: Optional[int] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    location_filter: str = "",
    employment_type_filter: str = "",
    include_undated: bool = True,
) -> dict[str, Any]:
    """
    Complete Stage 5 processing.

    Returns:
        {
            "jobs": [...],            # final, sorted, limited
            "excluded_by_date": int,  # jobs removed for being outside range
            "removed_duplicates": int,
            "removed_non_job": int,
        }
    """
    if not jobs:
        return {"jobs": [], "excluded_by_date": 0, "removed_duplicates": 0, "removed_non_job": 0}

    # 1. Normalize
    normalized_jobs = [normalize_job(job) for job in jobs]
    count_before_filter = len(normalized_jobs)

    # 2. Remove non-job content (safety pass)
    valid_jobs = filter_extracted_jobs(normalized_jobs)
    removed_non_job = count_before_filter - len(valid_jobs)

    # 3. Remove duplicate URLs
    count_before_dedup = len(valid_jobs)
    unique_jobs = remove_duplicates(valid_jobs)
    removed_duplicates = count_before_dedup - len(unique_jobs)

    # 4. Location / employment-type filters (Python string matching)
    if location_filter:
        loc = location_filter.lower().strip()
        unique_jobs = [
            j for j in unique_jobs
            if loc in j["location"].lower()
            or ("remote" in loc and "remote" in j["location"].lower())
        ]
    if employment_type_filter and employment_type_filter.lower() != "any":
        emp = employment_type_filter.lower()
        unique_jobs = [j for j in unique_jobs if emp in j["employment_type"].lower()]

    # 5. Date-range filter
    in_range_jobs, excluded_jobs = filter_by_date_range(
        unique_jobs, from_date=from_date, to_date=to_date, include_undated=include_undated
    )

    # 6. Relevance scoring
    scored_jobs = score_jobs(in_range_jobs, candidate)

    # 7. Sort (score desc, date desc)
    sorted_jobs = sort_jobs(scored_jobs)

    # 8. Limit + strip internal fields
    final_jobs = limit_jobs(sorted_jobs, max_jobs)
    for job in final_jobs:
        job.pop("_parsed_date", None)

    return {
        "jobs": final_jobs,
        "excluded_by_date": len(excluded_jobs),
        "removed_duplicates": removed_duplicates,
        "removed_non_job": removed_non_job,
    }


def get_job_statistics(jobs: list[dict]) -> dict:
    """Generate simple statistics for the UI."""
    total = len(jobs)
    with_date = sum(1 for job in jobs if normalize_date(job.get("posting_date")))
    without_date = total - with_date
    companies = {job.get("company") for job in jobs if job.get("company")}
    avg_match = round(sum(j.get("match_percent", 0) for j in jobs) / total) if total else 0

    return {
        "total_jobs": total,
        "jobs_with_date": with_date,
        "jobs_without_date": without_date,
        "unique_companies": len(companies),
        "average_match": avg_match,
    }
