"""
Job Field Extraction — Python-only (no LLM).
=================================================
Two-tier strategy:

1. **Structured data (best, most reliable):** Most ATS platforms
   (Greenhouse, Lever, Workday, SmartRecruiters, Workable, etc.) embed
   schema.org JobPosting JSON-LD in the page <script type="application/ld+json">.
   When present, this gives us exact title/company/location/date/type/
   description with zero guessing and zero LLM cost.

2. **Heuristic fallback:** If no JSON-LD is found, we fall back to
   <title>, <meta property="og:title">/<meta name="description">, and
   simple regex/keyword scanning of the visible text for employment type
   and date-like phrases. Fields we can't reliably determine are marked
   "not available" — never fabricated per BRD rule.
"""

from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

_EMPLOYMENT_TYPE_PATTERNS = {
    "Full-time": r"\bfull[\s-]?time\b",
    "Part-time": r"\bpart[\s-]?time\b",
    "Contract": r"\bcontract(or)?\b",
    "Internship": r"\bintern(ship)?\b",
    "Remote": r"\bremote\b",
    "Hybrid": r"\bhybrid\b",
    "On-site": r"\bon[\s-]?site\b",
}

_DATE_TEXT_PATTERN = re.compile(
    r"(posted\s+[\w\s,]{0,25}\bago\b|"
    r"posted\s+(today|yesterday)|"
    r"\b\d{1,2}\s+(days?|weeks?|months?|hours?)\s+ago\b|"
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\b|"
    r"\b\d{4}-\d{2}-\d{2}\b)",
    re.I,
)


def _extract_json_ld_jobpostings(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    postings = []

    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            continue

        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") in ("JobPosting", ["JobPosting"]):
                postings.append(item)
            # Sometimes wrapped in @graph
            elif isinstance(item, dict) and "@graph" in item:
                for sub in item["@graph"]:
                    if isinstance(sub, dict) and sub.get("@type") == "JobPosting":
                        postings.append(sub)

    return postings


def _flatten_location(job_location) -> str:
    if not job_location:
        return ""
    if isinstance(job_location, list):
        job_location = job_location[0] if job_location else {}
    if isinstance(job_location, dict):
        address = job_location.get("address", {})
        if isinstance(address, dict):
            parts = [
                address.get("addressLocality", ""),
                address.get("addressRegion", ""),
                address.get("addressCountry", ""),
            ]
            return ", ".join(p for p in parts if p)
    if isinstance(job_location, str):
        return job_location
    return ""


def _from_json_ld(posting: dict, fallback_url: str) -> dict:
    org = posting.get("hiringOrganization", {})
    company = org.get("name") if isinstance(org, dict) else org

    location = _flatten_location(posting.get("jobLocation"))
    if not location and posting.get("applicantLocationRequirements"):
        location = "Remote"

    description = posting.get("description", "") or ""
    description = BeautifulSoup(description, "html.parser").get_text(separator=" ")
    description = " ".join(description.split())
    if len(description) > 600:
        description = description[:600] + "..."

    employment_type = posting.get("employmentType", "")
    if isinstance(employment_type, list):
        employment_type = ", ".join(employment_type)

    date_posted = posting.get("datePosted", "") or "date not available"

    return {
        "title": (posting.get("title") or "Title not available").strip(),
        "company": (company or "Company not available").strip(),
        "location": (location or "Location not available").strip(),
        "employment_type": (employment_type or "Not available").strip(),
        "description": description or "Description not available",
        "posting_date": date_posted,
        "url": posting.get("url") or fallback_url,
        "extraction_method": "structured_data (schema.org JobPosting)",
    }


def _heuristic_extract(html: str, text: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    # Title
    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title["content"].strip()
    elif soup.title and soup.title.string:
        title = soup.title.string.strip()
    title = re.sub(r"\s*[-|]\s*(LinkedIn|Indeed|Glassdoor).*$", "", title, flags=re.I)

    # Description (meta)
    description = ""
    meta_desc = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", property="og:description")
    if meta_desc and meta_desc.get("content"):
        description = meta_desc["content"].strip()
    if not description:
        description = " ".join(text.split()[:120])

    # Employment type via keyword scan
    employment_type = "Not available"
    for label, pattern in _EMPLOYMENT_TYPE_PATTERNS.items():
        if re.search(pattern, text, re.I):
            employment_type = label
            break

    # Date phrase scan
    date_match = _DATE_TEXT_PATTERN.search(text)
    posting_date = date_match.group(0).strip() if date_match else "date not available"

    return {
        "title": title or "Title not available",
        "company": "Company not available",
        "location": "Location not available",
        "employment_type": employment_type,
        "description": description[:600] or "Description not available",
        "posting_date": posting_date,
        "url": url,
        "extraction_method": "heuristic (meta tags + text scan)",
    }


def extract_job(html: str, text: str, url: str) -> dict:
    """
    Extracts a single best job record from a fetched page.
    Prefers schema.org JSON-LD; falls back to heuristics.
    """
    postings = _extract_json_ld_jobpostings(html)
    if postings:
        return _from_json_ld(postings[0], url)
    return _heuristic_extract(html, text, url)
