"""
Job Search (BRD Sections 6, 8, 9) - Python implementation, NO LLM agent.
============================================================================
Previously this stage ran a full LangGraph ReAct agent (LLM reasoning loop
+ tool calls) just to call Tavily search. That burns LLM tokens for a task
that is a single deterministic API call per query.

This version calls the Tavily search API directly for each optimized
query, merges + dedupes the raw results in Python, and applies the
job_filter heuristics before anything gets scraped. Zero LLM calls here.
"""

from __future__ import annotations

from tavily import TavilyClient

from src.config import settings
from src.processors.job_filter import filter_search_results, is_trusted_domain


def run_job_search(
    queries: list[str],
    max_results_per_query: int = 5,
    time_range: str | None = "week",
) -> list[dict]:
    """
    Executes each query against Tavily directly (pure API call, no LLM),
    merges results, and applies Python-based filtering.

    time_range biases Tavily's own index toward recently published/updated
    pages ("day", "week", "month", "year", or None for no bias). This is
    the fix for stale evergreen career pages dominating results — without
    it, Tavily ranks by relevance only and can surface pages that are
    months old. The exact per-job posting date is still enforced later,
    precisely, by src/processors/date_filter.py on the scraped/extracted
    date — time_range here is just a search-side freshness hint, not the
    final cutoff.

    Returns a list of {"title", "url", "snippet"} dicts, trusted job
    domains sorted first.
    """
    client = TavilyClient(api_key=settings.TAVILY_API_KEY)

    raw_results: list[dict] = []
    seen_urls: set[str] = set()

    for query in queries:
        search_kwargs = dict(
            query=query,
            search_depth="basic",
            max_results=max_results_per_query,
        )
        if time_range:
            search_kwargs["time_range"] = time_range

        try:
            response = client.search(**search_kwargs)
        except Exception as exc:  # noqa: BLE001 - surface but keep going
            print(f"[job_search] Tavily query failed: {query!r} -> {exc}")
            continue

        for item in response.get("results", []):
            url = (item.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            raw_results.append({
                "title": item.get("title", "").strip(),
                "url": url,
                "snippet": item.get("content", "").strip(),
                "source_query": query,
            })

    filtered = filter_search_results(raw_results)

    # Trusted job boards / ATS platforms first.
    filtered.sort(key=lambda item: 0 if is_trusted_domain(item["url"]) else 1)

    return filtered
