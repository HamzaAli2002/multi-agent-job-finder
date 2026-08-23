from datetime import datetime

from src.pipeline import _infer_time_range


def test_infer_time_range_day():
    assert _infer_time_range(datetime(2026, 8, 22), datetime(2026, 8, 23)) == "day"


def test_infer_time_range_week():
    assert _infer_time_range(datetime(2026, 8, 17), datetime(2026, 8, 23)) == "week"


def test_infer_time_range_month():
    assert _infer_time_range(datetime(2026, 8, 1), datetime(2026, 8, 23)) == "month"


def test_infer_time_range_none_when_no_from_date():
    assert _infer_time_range(None, None) is None
