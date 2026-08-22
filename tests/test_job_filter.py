from src.processors.job_filter import filter_search_results, is_blocked_url, looks_like_job_title


def test_blocks_known_non_job_domains():
    assert is_blocked_url("https://github.com/someuser/somerepo") is True
    assert is_blocked_url("https://medium.com/@author/some-tutorial") is True
    assert is_blocked_url("https://en.wikipedia.org/wiki/Python") is True


def test_allows_legit_job_domains():
    assert is_blocked_url("https://boards.greenhouse.io/company/jobs/123") is False
    assert is_blocked_url("https://www.linkedin.com/jobs/view/123456") is False


def test_looks_like_job_title():
    assert looks_like_job_title("Junior Python Developer") is True
    assert looks_like_job_title("How to become a Python Developer") is False
    assert looks_like_job_title("Top 10 Python Tutorials for Beginners") is False


def test_filter_search_results_removes_blocked_and_bad_titles():
    results = [
        {"title": "Junior Python Developer", "url": "https://boards.greenhouse.io/acme/jobs/1"},
        {"title": "How to learn Python fast", "url": "https://medium.com/blog/python"},
        {"title": "Python Backend Engineer", "url": "https://github.com/acme/careers"},
    ]
    filtered = filter_search_results(results)
    urls = {r["url"] for r in filtered}
    assert "https://boards.greenhouse.io/acme/jobs/1" in urls
    assert len(filtered) == 1
