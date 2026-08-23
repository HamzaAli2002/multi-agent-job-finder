"""
Search Query Optimization (BRD Section 10)
==============================================
Pure Python. Turns a weak query ("Python jobs") into a specific one
("Junior Python Backend Developer Django FastAPI jobs Karachi") by
combining: experience level + role + top technologies + location +
"jobs"/"careers"/"hiring" intent keyword.

No LLM call — just deterministic string composition from the candidate
profile that the (single) analyzer LLM call already produced.
"""

from __future__ import annotations

_INTENT_KEYWORDS = ["jobs", "careers", "hiring", "openings"]


def build_optimized_queries(
    role: str,
    experience_level: str,
    skills: list[str],
    location: str,
    max_queries: int = 6,
) -> list[str]:
    """
    Builds a ranked list of specific, high-signal search queries.
    """
    role = (role or "Software Developer").strip()
    experience_level = (experience_level or "").strip()
    location = (location or "").strip()
    top_skills = [s.strip() for s in (skills or []) if s and s.strip()][:4]

    queries: list[str] = []

    # 1. Most specific: experience + role + top 2 technologies + location + jobs
    parts = []
    if experience_level:
        parts.append(experience_level)
    parts.append(role)
    parts.extend(top_skills[:2])
    if location:
        parts.append(location)
    parts.append("jobs")
    queries.append(" ".join(parts))

    # 2. Freshness-biased: role + "new jobs today" — placed early (not
    #    last) so it never gets cut off by max_queries. This, combined
    #    with the time_range param passed to Tavily at the API-call
    #    level, is what actually surfaces just-posted listings instead
    #    of old evergreen career pages.
    queries.append(f"{role} new jobs today")

    # 3. Role + top 3 technologies + "jobs"
    parts = [role] + top_skills[:3] + ["jobs"]
    queries.append(" ".join(parts))

    # 4. Role + location + "hiring"
    if location:
        queries.append(f"{role} {location} hiring")

    # 5. Role + "remote jobs" (broaden if candidate open to remote)
    queries.append(f"{role} remote jobs")

    # 6. Experience + role + "careers" + each remaining skill combos
    if experience_level:
        queries.append(f"{experience_level} {role} careers")

    # 7. Role + all top skills combined + "openings"
    if top_skills:
        queries.append(f"{role} {' '.join(top_skills)} openings")

    # De-duplicate while preserving order, collapse whitespace.
    seen = set()
    cleaned = []
    for q in queries:
        q = " ".join(q.split())
        key = q.lower()
        if q and key not in seen:
            seen.add(key)
            cleaned.append(q)

    return cleaned[:max_queries]
