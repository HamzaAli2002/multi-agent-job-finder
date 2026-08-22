"""
Duplicate Job Removal (BRD Section 12)
========================================
Pure Python. URL normalization + set/hash based duplicate detection.
Also catches "same job, different query" cases where the URL differs only
by tracking parameters, trailing slashes, or www./https vs http.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

# Query params that don't change job identity (tracking / referral params).
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gh_src", "ref", "referrer", "source", "trk", "fbclid", "gclid", "src",
}


def normalize_url(url: str) -> str:
    """Canonicalize a URL so equivalent job links collapse to one string."""
    if not url:
        return ""

    url = url.strip()
    parsed = urlparse(url)

    scheme = "https"  # treat http/https as equivalent
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]

    path = re.sub(r"/+$", "", parsed.path)  # drop trailing slash

    # Strip tracking params, keep meaningful ones (e.g. job id), sort for stability.
    kept_params = [
        (k, v) for k, v in parse_qsl(parsed.query)
        if k.lower() not in _TRACKING_PARAMS
    ]
    kept_params.sort()
    query = urlencode(kept_params)

    return urlunparse((scheme, netloc, path, "", query, ""))


def _content_fingerprint(job: dict) -> str:
    """Fallback fingerprint for jobs missing a URL: title + company."""
    title = str(job.get("title", "")).strip().lower()
    company = str(job.get("company", "")).strip().lower()
    raw = f"{title}|{company}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def remove_duplicates(jobs: list[dict]) -> list[dict]:
    """
    Remove duplicate job postings using normalized-URL set/hash matching.
    If a job has no URL, falls back to a title+company fingerprint so we
    still avoid showing the same job twice.
    """
    seen: set[str] = set()
    unique_jobs: list[dict] = []

    for job in jobs:
        url = job.get("url", "")
        key = normalize_url(url) if url else _content_fingerprint(job)

        if not key or key in seen:
            continue

        seen.add(key)
        unique_jobs.append(job)

    return unique_jobs
