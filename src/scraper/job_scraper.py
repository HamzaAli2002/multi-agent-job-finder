"""
Job Scraper (BRD Section 9) — Python only, no LLM agent loop.

Previous version ran a full LangGraph ReAct agent that called an LLM once
per URL to "decide" how to extract fields. This version fetches each URL
directly and extracts fields with job_extractor (schema.org JSON-LD first,
heuristic fallback second) — deterministic and free of per-page LLM cost.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

from src.processors.job_filter import is_blocked_url
from src.scraper.job_extractor import extract_job
from src.scraper.page_fetcher import fetch_page


def _scrape_one(item: dict) -> dict | None:
    url = item.get("url", "")
    if not url or is_blocked_url(url):
        return None

    page = fetch_page(url)
    if not page["ok"]:
        # Keep the URL with unavailable fields per BRD rule 14, rather
        # than dropping it silently.
        return {
            "title": item.get("title") or "Title not available",
            "company": "Company not available",
            "location": "Location not available",
            "employment_type": "Not available",
            "description": item.get("snippet", "") or "Description not available",
            "posting_date": "date not available",
            "url": url,
            "extraction_method": "search_snippet_fallback",
        }

    job = extract_job(page["html"], page["text"], page["final_url"])

    # If title extraction failed but the search result had one, use it.
    if job["title"] == "Title not available" and item.get("title"):
        job["title"] = item["title"]

    return job


def scrape_jobs(search_results: list[dict], max_workers: int = 6) -> list[dict]:
    """
    Fetches and extracts structured job data for each search result URL,
    in parallel (I/O-bound, thread pool — not LLM calls, so this is cheap
    and fast).
    """
    jobs: list[dict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_scrape_one, item): item for item in search_results}
        for future in as_completed(futures):
            try:
                result = future.result()
            except Exception as exc:  # noqa: BLE001
                print(f"[job_scraper] extraction failed: {exc}")
                result = None
            if result:
                jobs.append(result)

    return jobs
