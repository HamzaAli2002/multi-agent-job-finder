# 🧭 Job Finder — Resume → Date-Filtered, Ranked Job Results

A resume-driven job discovery system built around a simple principle:
**use an LLM only where an LLM is actually needed.** One Gemini call
reads the resume and builds a candidate profile. Everything after that
— query building, web search, scraping, non-job filtering, date-range
filtering, duplicate removal, and relevance ranking — is deterministic
Python.

This is an improved version of the original
[Multi-Agent-Job-Finder](https://github.com/msncoder/Multi-Agent-Job-Finder)
project, rebuilt to satisfy the assignment BRD: minimum LLM/API usage,
maximum Python-based processing, specific date-range job filtering, and
a clean, transparent-themed Streamlit interface.

---

## Overview

```
Resume Upload
   -> Resume Text Extraction (Python: pypdf / python-docx)
   -> Candidate Profile Analysis (1x Gemini call — the ONLY LLM call)
   -> Search Query Optimization (Python)
   -> Job Search (Tavily API, direct calls — no LLM agent loop)
   -> Non-Job Content Filtering (Python)
   -> Scraping + Structured Field Extraction (Python: schema.org JSON-LD
      first, heuristic fallback second — no LLM per page)
   -> Duplicate Removal (URL normalization + hash/set matching)
   -> Date-Range Filtering (handles absolute + relative dates)
   -> Relevance Scoring (weighted algorithm)
   -> Final Ranked Job Table (Streamlit)
```

---

## Why this is "minimum LLM usage"

The original project ran two separate LangGraph **ReAct agents** — one
for search, one for scraping — meaning the LLM was making tool-call
decisions and reasoning on *every single search query and every single
scraped page*. That's a lot of avoidable model calls for work that
Python already does reliably.

This version keeps exactly **one** LLM call per run (resume analysis)
and replaces both agents with plain Python:

| Stage | Before | Now |
|---|---|---|
| Resume analysis | 1 Gemini call | 1 Gemini call *(kept — genuinely needs judgment)* |
| Search | Gemini ReAct agent + Tavily tool | Direct Tavily API call, Python-merged & filtered |
| Scraping / extraction | Gemini ReAct agent + scrape tool, 1 LLM call per page | Direct HTTP fetch + schema.org JSON-LD / heuristic extraction, **0 LLM calls** |
| Filtering, dedup, dates, ranking | Partial Python | Fully Python |

---

## Key Features

- Upload resumes in PDF or DOCX format
- Single-pass candidate profile extraction (role, experience level,
  location, employment type, skills)
- Python query optimizer that turns a weak query like `"Python jobs"`
  into a specific one like `"Junior Python Backend Developer Django
  FastAPI jobs Karachi"`
- Direct Tavily search calls (no per-query LLM reasoning)
- Non-job content filtering — blogs, tutorials, courses, documentation,
  GitHub repos, and generic news/articles are dropped before scraping
- Structured job-page extraction:
  - **Tier 1:** schema.org `JobPosting` JSON-LD (used by Greenhouse,
    Lever, Workday, SmartRecruiters, Workable and most modern ATS
    platforms) — exact fields, zero guessing
  - **Tier 2:** heuristic fallback (meta tags + text pattern scanning)
    when no structured data is present
- Robust date normalization: absolute formats (`August 10, 2026`,
  `10 Aug 2026`, `2026-08-10`) **and** relative formats (`Posted 3 days
  ago`, `Posted yesterday`) — normalized against today's date
- Specific date-range filtering (`From Date` → `To Date`), inclusive,
  never fabricates a date it can't verify
- URL-normalization + hash-based duplicate removal (handles tracking
  params, `www.`, `http` vs `https`, trailing slashes)
- Weighted relevance scoring (job title, technology, skills, location,
  experience level, employment type) → 0–100% match score
- Configurable **Maximum Jobs** and **Search Results per query**
- Location and employment-type filters
- Live progress checklist while the pipeline runs
- Final results as a clean table (Job / Company / Date / Location /
  Match / Link) plus card view, with CSV export
- Transparent glass-style Streamlit theme

---

## Installation

```bash
git clone <your-repo-url>
cd Multi-Agent-Job-Finder
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Environment Setup

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

```env
GOOGLE_API_KEY=your_google_api_key_here
MODEL_NAME=gemini-3.6-flash
TEMPERATURE=0.3

TAVILY_API_KEY=your_tavily_api_key_here

MAX_SEARCH_RESULTS=5
MAX_QUERIES=6
SCRAPE_MAX_WORKERS=6
```

`GOOGLE_API_KEY` is only used for the one-time resume analysis call.
`TAVILY_API_KEY` powers the Python-only search stage.

**Never commit your `.env` file, API keys, passwords, or session
data.** `.gitignore` already excludes `.env`.

## Run Instructions

```bash
streamlit run app.py
```

Then open the local URL Streamlit prints (usually `http://localhost:8501`).

## Streamlit Usage

1. Set your search preferences in the sidebar: max search results per
   query, maximum final jobs, optional posting-date range, location
   filter, and employment type.
2. Upload a PDF or DOCX resume.
3. Click **Find Matching Jobs**.
4. Watch the live progress checklist as each stage completes.
5. Review the candidate profile, match insights, final job table, and
   job cards. Export results as CSV if needed.

## Search Configuration

- **Search Results per Query** — how many results Tavily returns per
  optimized query (raised = broader search, more Tavily calls).
- **Maximum Jobs** — cap on the final ranked list shown to the user.
- These are fully dynamic from the sidebar — no code changes needed.

## Date Filtering

The date filter (`src/processors/date_filter.py`) normalizes whatever
format a job page provides — absolute dates, relative phrases like
"Posted 3 days ago", "yesterday", "2 weeks ago" — into a real
`datetime`, then keeps only jobs whose posting date falls inside the
selected `[From Date, To Date]` range (inclusive). If a job's date
can't be reliably determined, it is labeled `"date not available"` and
is **never guessed** — you choose in the sidebar whether such jobs are
included or excluded from results.

## Technologies Used

- **Streamlit** — UI
- **LangChain + `langchain-google-genai`** — the single resume-analysis call
- **Tavily API** — web search (direct Python calls, no agent loop)
- **Requests + BeautifulSoup** — page fetching & structured/heuristic extraction
- **pypdf / python-docx** — resume parsing
- **Pandas** — results table & CSV export
- **Pydantic Settings** — environment/config management
- **Pytest** — unit + integration tests for all Python algorithms

## API Requirements

| Service | Used for | Calls per run |
|---|---|---|
| Google Gemini | Resume → candidate profile | 1 |
| Tavily | Job search | 1 per optimized query (≈4–6) |

No LLM calls happen during scraping, filtering, deduplication, date
filtering, or ranking.

## Testing

```bash
pytest tests/ -v
```

Covers: date normalization (absolute + relative + unavailable),
date-range filtering, URL normalization & duplicate removal, non-job
content filtering, relevance scoring, and a full Stage-5 processing
integration test — all without any network or API calls.

## Limitations

- LinkedIn and Indeed require authenticated sessions for full listing
  access; per the BRD's security requirement, this project does not
  automate logins or store credentials. Job discovery on those
  platforms happens through Tavily's public search index rather than
  direct authenticated scraping.
- Heuristic extraction (Tier 2, used when a page has no schema.org
  data) is best-effort — some fields may come back as "not available"
  rather than a guess.
- Relevance scoring is a transparent weighted heuristic, not a
  semantic/embedding model — it favors precision (avoiding wrong
  guesses) over recall.

## Future Improvements

- Optional Playwright-based rendering for JS-heavy job boards
- Company/domain allow-list customization from the UI
- Persisted search history and saved candidate profiles
- Embedding-based semantic matching as an opt-in alternative scorer

---

## Project Structure

```
app.py                          # Streamlit UI (transparent theme)
src/
  config.py                     # Settings (.env driven)
  pipeline.py                   # Orchestrates all stages + progress callback
  chains/analyzer.py            # THE single LLM call (resume -> profile)
  search/
    query_optimizer.py          # Python query optimization
    job_search.py                # Direct Tavily calls, Python filtering
  scraper/
    page_fetcher.py              # HTTP fetch + HTML cleanup
    job_extractor.py             # schema.org JSON-LD + heuristic extraction
    job_scraper.py                # Orchestrates fetch+extract per URL
  processors/
    job_filter.py                 # Non-job content filtering
    duplicate_removal.py          # URL normalization + dedup
    date_filter.py                 # Absolute + relative date normalization/range
    relevance_scorer.py            # Weighted match scoring
    job_result_processor.py        # Orchestrates Stage 5
  tools/resume_reader.py          # PDF/DOCX text extraction
tests/                             # Pytest suite (no network required)
```
