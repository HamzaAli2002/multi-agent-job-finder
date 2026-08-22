"""
Page Fetcher — Python-only HTTP + HTML cleanup (BRD Section 9).
No LLM involved. Returns both raw HTML (for structured-data extraction)
and clean visible text (for heuristic fallback extraction).
"""

from __future__ import annotations

from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

REQUEST_TIMEOUT = 15
MAX_TEXT_LENGTH = 12000

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def validate_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def clean_page_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for element in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "aside", "form"]):
        element.decompose()

    text = soup.get_text(separator="\n")

    lines = []
    for line in text.splitlines():
        line = " ".join(line.split())
        if line:
            lines.append(line)

    cleaned = []
    for line in lines:
        if not cleaned or line != cleaned[-1]:
            cleaned.append(line)

    return "\n".join(cleaned)


def fetch_page(url: str) -> dict:
    """
    Returns:
        {
          "ok": bool,
          "final_url": str,
          "html": str,          # raw HTML (for JSON-LD / meta parsing)
          "text": str,          # cleaned visible text (truncated)
          "error": str | None,
        }
    """
    if not validate_url(url):
        return {"ok": False, "final_url": url, "html": "", "text": "", "error": "Invalid URL"}

    try:
        response = requests.get(
            url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        return {"ok": False, "final_url": url, "html": "", "text": "", "error": str(exc)}

    html = response.text
    text = clean_page_text(html)
    if len(text) > MAX_TEXT_LENGTH:
        text = text[:MAX_TEXT_LENGTH] + "\n\n[truncated]"

    return {"ok": True, "final_url": response.url, "html": html, "text": text, "error": None}
