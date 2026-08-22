"""
Job Filtering (BRD Section 11)
=================================
Pure Python heuristics to remove non-job content before scraping (saves
requests) and again after extraction (in case a page slipped through).

Removed: blogs, tutorials, courses, documentation, GitHub repos,
generic articles / news.

Preferred: actual job postings, company career pages, legitimate job
boards, recruitment platforms.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Domains that are almost never a real job posting.
_BLOCKED_DOMAINS = {
    "github.com", "gitlab.com", "bitbucket.org",
    "medium.com", "dev.to", "hashnode.com", "substack.com",
    "youtube.com", "youtu.be",
    "wikipedia.org",
    "coursera.org", "udemy.com", "udacity.com", "edx.org", "khanacademy.org",
    "docs.python.org", "developer.mozilla.org", "readthedocs.io",
    "stackoverflow.com", "stackexchange.com", "quora.com",
    "reddit.com",
    "facebook.com", "twitter.com", "x.com", "instagram.com", "tiktok.com",
    "pinterest.com",
}

# Recognized legitimate job platforms / ATS providers get a trust boost.
_TRUSTED_JOB_DOMAINS = {
    "linkedin.com", "indeed.com", "glassdoor.com", "ziprecruiter.com",
    "greenhouse.io", "lever.co", "workday.com", "myworkdayjobs.com",
    "smartrecruiters.com", "workable.com", "bamboohr.com",
    "rozee.pk", "mustakbil.com", "bayt.com", "monster.com",
    "angel.co", "wellfound.com", "remoteok.com", "weworkremotely.com",
    "dice.com", "simplyhired.com", "careerjet.com", "jobs.lever.co",
}

_BAD_PATH_KEYWORDS = (
    "/blog/", "/tutorial", "/course", "/docs/", "/documentation",
    "/news/", "/article", "/wiki/", "/guide/", "/how-to", "/learn/",
)

_BAD_TITLE_KEYWORDS = (
    "how to", "tutorial", "top 10", "top 20", "best practices",
    "beginner's guide", "ultimate guide", "vs ", "cheat sheet",
    "roadmap", "course", "certification", "interview questions",
    "news", "announcement",
)

_GOOD_TITLE_KEYWORDS = (
    "job", "career", "hiring", "vacancy", "opening", "position",
    "developer", "engineer", "analyst", "intern", "specialist",
    "apply", "recruitment",
)


def _domain(url: str) -> str:
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc[4:] if netloc.startswith("www.") else netloc
    except Exception:
        return ""


def is_blocked_url(url: str) -> bool:
    domain = _domain(url)
    if any(domain == d or domain.endswith("." + d) for d in _BLOCKED_DOMAINS):
        return True
    lowered_url = url.lower()
    if any(kw in lowered_url for kw in _BAD_PATH_KEYWORDS):
        return True
    return False


def is_trusted_domain(url: str) -> bool:
    domain = _domain(url)
    return any(domain == d or domain.endswith("." + d) for d in _TRUSTED_JOB_DOMAINS)


def looks_like_job_title(title: str) -> bool:
    if not title:
        return False
    lowered = title.lower()
    if any(kw in lowered for kw in _BAD_TITLE_KEYWORDS):
        return False
    if any(kw in lowered for kw in _GOOD_TITLE_KEYWORDS):
        return True
    # Neutral titles (e.g. just a role name like "Python Developer") are ok.
    return True


def filter_search_results(results: list[dict]) -> list[dict]:
    """Filter raw search results (title/url pairs) before scraping."""
    filtered = []
    for item in results:
        url = item.get("url", "")
        title = item.get("title", "")
        if not url or is_blocked_url(url):
            continue
        if title and not looks_like_job_title(title):
            continue
        filtered.append(item)
    return filtered


def filter_extracted_jobs(jobs: list[dict]) -> list[dict]:
    """Final safety pass after scraping/extraction."""
    return [
        job for job in jobs
        if job.get("url") and not is_blocked_url(job["url"])
    ]
