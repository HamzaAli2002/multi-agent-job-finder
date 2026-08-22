"""
Job Relevance Algorithm (BRD Section 13)
============================================
Pure Python weighted scoring. No LLM call.

Signal                    Suggested Score
-----------------------   ---------------
Job Title Match            +30
Required Technology        +20
Skill Match                +10
Location Match             +10
Experience Match           +10
Employment Type Match      +5

Final score is normalized to a 0-100 percentage for display ("Match %").
"""

from __future__ import annotations

import re

_WEIGHTS = {
    "title": 30,
    "technology": 20,
    "skill": 10,
    "location": 10,
    "experience": 10,
    "employment_type": 5,
}

_MAX_SCORE = sum(_WEIGHTS.values())  # 85

_EXPERIENCE_LEVELS = {
    "intern": 0, "internship": 0, "entry": 1, "junior": 1, "fresher": 1,
    "mid": 2, "mid-level": 2, "intermediate": 2,
    "senior": 3, "sr": 3, "lead": 4, "principal": 4, "staff": 4,
}


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9+.#]{1,}", (text or "").lower()))


def _experience_rank(text: str) -> int | None:
    lowered = (text or "").lower()
    for keyword, rank in sorted(_EXPERIENCE_LEVELS.items(), key=lambda x: -len(x[0])):
        if keyword in lowered:
            return rank
    return None


def score_job(job: dict, candidate: dict) -> dict:
    """
    Returns the job dict augmented with:
        - relevance_score (raw points, 0..85)
        - match_percent   (0..100, for UI display)
        - match_breakdown (dict of which signals hit)
    """
    title = job.get("title", "")
    description = job.get("description", "")
    job_location = job.get("location", "")
    employment_type = job.get("employment_type", "")
    job_text = f"{title} {description}"

    role = candidate.get("role", "")
    skills = candidate.get("skills", []) or []
    candidate_location = candidate.get("location", "")
    experience_level = candidate.get("experience_level", "")
    preferred_employment_type = candidate.get("employment_type", "")

    job_tokens = _tokenize(job_text)
    role_tokens = _tokenize(role)
    skill_tokens = {s.lower().strip() for s in skills if s}

    breakdown = {}
    score = 0

    # --- Job Title Match -----------------------------------------------
    title_tokens = _tokenize(title)
    title_hit = bool(role_tokens & title_tokens) or (
        role.lower().strip() and role.lower().strip() in title.lower()
    )
    if title_hit:
        score += _WEIGHTS["title"]
    breakdown["title_match"] = title_hit

    # --- Required Technology + Skill Match ------------------------------
    matched_skills = skill_tokens & job_tokens
    tech_hit = len(matched_skills) >= 2
    skill_hit = len(matched_skills) >= 1
    if tech_hit:
        score += _WEIGHTS["technology"]
    elif skill_hit:
        score += _WEIGHTS["skill"]
    breakdown["technology_match"] = tech_hit
    breakdown["skill_match"] = skill_hit
    breakdown["matched_skills"] = sorted(matched_skills)

    # --- Location Match ---------------------------------------------------
    location_hit = False
    if candidate_location and job_location:
        cand_loc = candidate_location.lower()
        job_loc = job_location.lower()
        if cand_loc in job_loc or job_loc in cand_loc:
            location_hit = True
        if "remote" in cand_loc and "remote" in job_loc:
            location_hit = True
    if location_hit:
        score += _WEIGHTS["location"]
    breakdown["location_match"] = location_hit

    # --- Experience Match ---------------------------------------------------
    exp_hit = False
    cand_rank = _experience_rank(experience_level)
    job_rank = _experience_rank(job_text)
    if cand_rank is not None and job_rank is not None and cand_rank == job_rank:
        exp_hit = True
    if exp_hit:
        score += _WEIGHTS["experience"]
    breakdown["experience_match"] = exp_hit

    # --- Employment Type Match --------------------------------------------
    emp_hit = False
    if preferred_employment_type and employment_type:
        if preferred_employment_type.lower().strip() in employment_type.lower():
            emp_hit = True
    if emp_hit:
        score += _WEIGHTS["employment_type"]
    breakdown["employment_type_match"] = emp_hit

    match_percent = round((score / _MAX_SCORE) * 100)

    job["relevance_score"] = score
    job["match_percent"] = match_percent
    job["match_breakdown"] = breakdown
    return job


def score_jobs(jobs: list[dict], candidate: dict) -> list[dict]:
    return [score_job(job, candidate) for job in jobs]
