"""Unit tests for X-Ray query generation."""

from app.models.jd import ExperienceRange, JobRequirements
from app.services.query_generator import LINKEDIN_XRAY_SITE, generate_xray_queries
from app.utils.text_utils import expand_locations


SAMPLE_REQUIREMENTS = JobRequirements(
    job_titles=["Windchill Developer", "PLM Developer"],
    technical_skills=["Windchill", "PDMLink", "Java"],
    preferred_skills=["OIR", "Workflows"],
    locations=["Texas", "Dallas"],
    experience=ExperienceRange(min_years=3, max_years=8),
    exclusions=["intern", "fresher"],
)


def test_queries_contain_linkedin_site():
    queries = generate_xray_queries(SAMPLE_REQUIREMENTS, max_queries=5)
    assert len(queries) >= 1
    for query in queries:
        assert LINKEDIN_XRAY_SITE in query


def test_queries_contain_skills():
    queries = generate_xray_queries(SAMPLE_REQUIREMENTS, max_queries=5)
    combined = " ".join(queries)
    assert "Windchill" in combined
    assert "Java" in combined or "PDMLink" in combined


def test_queries_contain_location():
    queries = generate_xray_queries(SAMPLE_REQUIREMENTS, max_queries=5)
    combined = " ".join(queries)
    assert "Texas" in combined or "Dallas" in combined


def test_queries_contain_exclusions():
    queries = generate_xray_queries(SAMPLE_REQUIREMENTS, max_queries=5)
    combined = " ".join(queries)
    assert "-intern" in combined
    assert "-fresher" in combined


def test_queries_deduplicated():
    queries = generate_xray_queries(SAMPLE_REQUIREMENTS, max_queries=5)
    assert len(queries) == len(set(queries))


def test_max_queries_respected():
    queries = generate_xray_queries(SAMPLE_REQUIREMENTS, max_queries=2)
    assert len(queries) <= 2


def test_expand_locations_splits_country():
    assert expand_locations(["Texas, US", "Dallas"]) == ["Texas", "Dallas"]


def test_does_not_quote_texas_us_as_single_phrase():
    req = JobRequirements(
        job_titles=["Windchill Developer"],
        technical_skills=["Windchill", "Java"],
        locations=["Texas, US"],
    )
    queries = generate_xray_queries(req, max_queries=5)
    combined = " ".join(queries)
    assert '"Texas, US"' not in combined
    assert "Texas" in combined
