"""
Date Filtering Algorithm (BRD Section 7)
=========================================

Pure Python, zero LLM usage.

Handles:
    - Absolute formats: "August 10, 2026", "10 Aug 2026", "2026-08-10",
      "10-08-2026", "08/10/2026" ...
    - Relative formats: "Posted 3 days ago", "Posted yesterday",
      "Posted today", "2 weeks ago", "1 month ago"
    - Missing / unverifiable dates -> returns None (never fabricated)

Pipeline: Job Date -> Normalize -> Compare From Date -> Compare To Date
          -> Inside Range? -> Keep / Remove
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Optional

DATE_NOT_AVAILABLE = "date not available"

_UNAVAILABLE_VALUES = {
    "",
    DATE_NOT_AVAILABLE,
    "not available",
    "unavailable",
    "unknown",
    "n/a",
    "na",
    "none",
    "not specified",
}

# Absolute date formats we accept, ordered most -> least specific.
_ABSOLUTE_FORMATS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%m/%d/%Y",
    "%B %d, %Y",     # August 10, 2026
    "%b %d, %Y",     # Aug 10, 2026
    "%d %B %Y",       # 10 August 2026
    "%d %b %Y",       # 10 Aug 2026
    "%B %d %Y",
    "%b %d %Y",
    "%Y-%m-%dT%H:%M:%S",   # ISO datetime (schema.org datePosted)
]

_RELATIVE_PATTERNS = [
    # "Posted 3 days ago", "3 days ago"
    (re.compile(r"(\d+)\s*day[s]?\s*ago", re.I), "days"),
    (re.compile(r"(\d+)\s*week[s]?\s*ago", re.I), "weeks"),
    (re.compile(r"(\d+)\s*month[s]?\s*ago", re.I), "months"),
    (re.compile(r"(\d+)\s*hour[s]?\s*ago", re.I), "hours"),
    (re.compile(r"(\d+)\s*minute[s]?\s*ago", re.I), "minutes"),
]


def _clean(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^posted\s*:?\s*", "", value, flags=re.I)
    value = re.sub(r"^published\s*:?\s*", "", value, flags=re.I)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_date(raw_value: Optional[str], reference: Optional[datetime] = None) -> Optional[datetime]:
    """
    Normalize a raw posting-date string into a datetime object.

    Returns None if the date cannot be reliably determined.
    Never guesses / fabricates a date.
    """
    if not raw_value or not isinstance(raw_value, str):
        return None

    reference = reference or datetime.now()
    value = _clean(raw_value)
    lowered = value.lower()

    if lowered in _UNAVAILABLE_VALUES:
        return None

    # --- Relative: today / yesterday -------------------------------------
    if lowered in {"today", "just posted", "posted today", "0 days ago"}:
        return reference
    if lowered in {"yesterday", "posted yesterday"}:
        return reference - timedelta(days=1)

    # --- Relative: "N units ago" -------------------------------------------
    for pattern, unit in _RELATIVE_PATTERNS:
        match = pattern.search(lowered)
        if match:
            n = int(match.group(1))
            if unit == "days":
                return reference - timedelta(days=n)
            if unit == "weeks":
                return reference - timedelta(weeks=n)
            if unit == "months":
                return reference - timedelta(days=n * 30)
            if unit == "hours":
                return reference - timedelta(hours=n)
            if unit == "minutes":
                return reference - timedelta(minutes=n)

    # --- ISO datetime with timezone/millis (schema.org) --------------------
    iso_candidate = re.sub(r"(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$", "", value)
    for fmt in _ABSOLUTE_FORMATS:
        try:
            return datetime.strptime(iso_candidate, fmt)
        except ValueError:
            continue

    # --- Absolute formats on the raw cleaned value --------------------------
    for fmt in _ABSOLUTE_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue

    return None


def is_within_range(
    parsed_date: Optional[datetime],
    from_date: Optional[datetime],
    to_date: Optional[datetime],
) -> bool:
    """
    True if parsed_date falls inside [from_date, to_date] (inclusive).
    If either bound is None, that side is unbounded.
    Jobs with no parsed date are handled by the caller (kept separately),
    this function only evaluates dated jobs.
    """
    if parsed_date is None:
        return False

    if from_date and parsed_date.date() < from_date.date():
        return False
    if to_date and parsed_date.date() > to_date.date():
        return False
    return True


def filter_by_date_range(
    jobs: list[dict],
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    include_undated: bool = True,
) -> tuple[list[dict], list[dict]]:
    """
    Splits jobs into (in_range, excluded) based on posting_date.

    - Jobs with a normalizable date inside [from_date, to_date] -> in_range
    - Jobs with a normalizable date outside the range -> excluded
    - Jobs with no reliable date -> in_range only if include_undated=True
      (they are never fabricated, just optionally surfaced separately)
    """
    in_range: list[dict] = []
    excluded: list[dict] = []

    if from_date is None and to_date is None:
        # No range specified: keep everything, still normalize for sorting.
        for job in jobs:
            job["_parsed_date"] = normalize_date(job.get("posting_date"))
            in_range.append(job)
        return in_range, excluded

    for job in jobs:
        parsed = normalize_date(job.get("posting_date"))
        job["_parsed_date"] = parsed

        if parsed is None:
            if include_undated:
                in_range.append(job)
            else:
                excluded.append(job)
            continue

        if is_within_range(parsed, from_date, to_date):
            in_range.append(job)
        else:
            excluded.append(job)

    return in_range, excluded
