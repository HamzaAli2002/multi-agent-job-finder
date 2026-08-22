from datetime import datetime

from src.processors.date_filter import filter_by_date_range, normalize_date


def test_normalize_absolute_formats():
    ref = datetime(2026, 8, 22)
    assert normalize_date("2026-08-10") == datetime(2026, 8, 10)
    assert normalize_date("10 Aug 2026") == datetime(2026, 8, 10)
    assert normalize_date("August 10, 2026") == datetime(2026, 8, 10)
    # DD/MM/YYYY is tried before MM/DD/YYYY (international format preferred)
    assert normalize_date("08/10/2026") == datetime(2026, 10, 8)


def test_normalize_relative_formats():
    ref = datetime(2026, 8, 22)
    assert normalize_date("Posted 3 days ago", reference=ref) == datetime(2026, 8, 19)
    assert normalize_date("Posted yesterday", reference=ref) == datetime(2026, 8, 21)
    assert normalize_date("2 weeks ago", reference=ref) == datetime(2026, 8, 8)


def test_normalize_unavailable_returns_none():
    assert normalize_date(None) is None
    assert normalize_date("") is None
    assert normalize_date("date not available") is None
    assert normalize_date("unknown") is None
    assert normalize_date("some gibberish text") is None


def test_filter_by_date_range_keeps_only_in_range():
    jobs = [
        {"title": "A", "posting_date": "2026-08-05"},
        {"title": "B", "posting_date": "2026-08-12"},
        {"title": "C", "posting_date": "2026-08-20"},
        {"title": "D", "posting_date": "date not available"},
    ]
    from_date = datetime(2026, 8, 1)
    to_date = datetime(2026, 8, 15)

    in_range, excluded = filter_by_date_range(jobs, from_date, to_date, include_undated=True)

    titles_in = {j["title"] for j in in_range}
    titles_out = {j["title"] for j in excluded}

    assert titles_in == {"A", "B", "D"}
    assert titles_out == {"C"}


def test_filter_by_date_range_excludes_undated_when_requested():
    jobs = [{"title": "D", "posting_date": "date not available"}]
    in_range, excluded = filter_by_date_range(
        jobs, datetime(2026, 8, 1), datetime(2026, 8, 15), include_undated=False
    )
    assert in_range == []
    assert len(excluded) == 1
