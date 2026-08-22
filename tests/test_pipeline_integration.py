from datetime import datetime

from src.processors.job_result_processor import get_job_statistics, process_jobs


def make_candidate():
    return {
        "role": "Python Developer",
        "skills": ["Python", "FastAPI", "Django"],
        "location": "Karachi",
        "experience_level": "Junior",
        "employment_type": "Full-time",
    }


def test_process_jobs_full_pipeline():
    jobs = [
        {
            "title": "Junior Python Developer",
            "company": "Acme",
            "location": "Karachi",
            "employment_type": "Full-time",
            "description": "FastAPI Django Python role",
            "posting_date": "2026-08-10",
            "url": "https://boards.greenhouse.io/acme/jobs/1",
        },
        {
            # duplicate of job 1 (tracking params only)
            "title": "Junior Python Developer",
            "company": "Acme",
            "location": "Karachi",
            "employment_type": "Full-time",
            "description": "FastAPI Django Python role",
            "posting_date": "2026-08-10",
            "url": "https://boards.greenhouse.io/acme/jobs/1?utm_source=x",
        },
        {
            # outside date range
            "title": "Senior Python Developer",
            "company": "Beta",
            "location": "Lahore",
            "employment_type": "Full-time",
            "description": "Python backend role",
            "posting_date": "2026-01-01",
            "url": "https://boards.greenhouse.io/beta/jobs/2",
        },
        {
            # blocked domain, should be filtered out
            "title": "Python Tutorial",
            "company": "N/A",
            "location": "N/A",
            "employment_type": "N/A",
            "description": "A tutorial, not a job",
            "posting_date": "date not available",
            "url": "https://github.com/someone/python-tutorial",
        },
    ]

    result = process_jobs(
        jobs,
        candidate=make_candidate(),
        max_jobs=10,
        from_date=datetime(2026, 8, 1),
        to_date=datetime(2026, 8, 20),
    )

    final_jobs = result["jobs"]
    titles = [j["title"] for j in final_jobs]

    assert titles == ["Junior Python Developer"]  # dedup + date filter + non-job filter
    assert result["removed_duplicates"] == 1
    assert result["excluded_by_date"] == 1
    assert result["removed_non_job"] == 1
    assert final_jobs[0]["match_percent"] > 0

    stats = get_job_statistics(final_jobs)
    assert stats["total_jobs"] == 1
    assert stats["unique_companies"] == 1
