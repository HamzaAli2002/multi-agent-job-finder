from src.search.query_optimizer import build_optimized_queries


def test_freshness_query_included_and_not_cut_off():
    queries = build_optimized_queries(
        role="Python Developer",
        experience_level="Junior",
        skills=["Python", "FastAPI", "Django", "PostgreSQL"],
        location="Karachi",
        max_queries=6,
    )
    assert any("new jobs today" in q.lower() for q in queries)


def test_queries_are_deduplicated_and_nonempty():
    queries = build_optimized_queries(
        role="Backend Developer",
        experience_level="",
        skills=[],
        location="",
        max_queries=6,
    )
    assert len(queries) > 0
    assert len(queries) == len(set(q.lower() for q in queries))
