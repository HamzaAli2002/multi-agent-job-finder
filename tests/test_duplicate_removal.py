from src.processors.duplicate_removal import normalize_url, remove_duplicates


def test_normalize_url_strips_www_and_tracking_params():
    a = normalize_url("https://www.example.com/jobs/123?utm_source=google")
    b = normalize_url("http://example.com/jobs/123")
    assert a == b


def test_normalize_url_strips_trailing_slash():
    a = normalize_url("https://example.com/jobs/123/")
    b = normalize_url("https://example.com/jobs/123")
    assert a == b


def test_remove_duplicates_by_url():
    jobs = [
        {"title": "Python Dev", "url": "https://example.com/jobs/1"},
        {"title": "Python Dev (dup)", "url": "https://www.example.com/jobs/1?utm_source=x"},
        {"title": "Backend Dev", "url": "https://example.com/jobs/2"},
    ]
    unique = remove_duplicates(jobs)
    assert len(unique) == 2


def test_remove_duplicates_fallback_to_title_company_when_no_url():
    jobs = [
        {"title": "Python Dev", "company": "Acme", "url": ""},
        {"title": "Python Dev", "company": "Acme", "url": ""},
        {"title": "Python Dev", "company": "Beta", "url": ""},
    ]
    unique = remove_duplicates(jobs)
    assert len(unique) == 2
