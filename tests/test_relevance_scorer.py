from src.processors.relevance_scorer import score_job


def make_candidate():
    return {
        "role": "Python Developer",
        "skills": ["Python", "FastAPI", "Django", "PostgreSQL"],
        "location": "Karachi",
        "experience_level": "Junior",
        "employment_type": "Full-time",
    }


def test_high_match_job_scores_higher():
    candidate = make_candidate()
    strong_job = {
        "title": "Junior Python Developer",
        "description": "Work with FastAPI and Django backend, PostgreSQL database.",
        "location": "Karachi, Pakistan",
        "employment_type": "Full-time",
    }
    weak_job = {
        "title": "Marketing Manager",
        "description": "Manage social media campaigns.",
        "location": "New York",
        "employment_type": "Contract",
    }

    strong_scored = score_job(dict(strong_job), candidate)
    weak_scored = score_job(dict(weak_job), candidate)

    assert strong_scored["match_percent"] > weak_scored["match_percent"]
    assert strong_scored["match_breakdown"]["title_match"] is True
    assert weak_scored["match_breakdown"]["title_match"] is False


def test_match_percent_bounded_0_100():
    candidate = make_candidate()
    job = {
        "title": "Junior Python Developer",
        "description": "Python FastAPI Django PostgreSQL",
        "location": "Karachi",
        "employment_type": "Full-time",
    }
    scored = score_job(job, candidate)
    assert 0 <= scored["match_percent"] <= 100
