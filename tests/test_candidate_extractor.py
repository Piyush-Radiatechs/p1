"""Unit tests for LinkedIn URL extraction from search results."""

from app.services.candidate_extractor import (
    extract_candidates_from_results,
    is_linkedin_profile_url,
    normalize_linkedin_url,
)


def test_normalize_profile_url():
    url = "https://www.linkedin.com/in/test-user/?utm_source=google"
    assert normalize_linkedin_url(url) == "https://www.linkedin.com/in/test-user"


def test_reject_company_url():
    assert normalize_linkedin_url("https://www.linkedin.com/company/example") is None


def test_reject_jobs_url():
    assert normalize_linkedin_url("https://www.linkedin.com/jobs/view/123") is None


def test_reject_school_url():
    assert normalize_linkedin_url("https://www.linkedin.com/school/example") is None


def test_is_linkedin_profile_url():
    assert is_linkedin_profile_url("https://www.linkedin.com/in/test-user") is True
    assert is_linkedin_profile_url("https://www.linkedin.com/company/example") is False


def test_extract_candidates_filters_non_profiles():
    results = [
        {"link": "https://www.linkedin.com/in/test-user", "title": "Dev", "snippet": "...", "position": 1, "query": "q1"},
        {"link": "https://www.linkedin.com/company/example", "title": "Co", "snippet": "...", "position": 2, "query": "q1"},
        {"link": "https://www.linkedin.com/jobs/view/123", "title": "Job", "snippet": "...", "position": 3, "query": "q1"},
    ]
    candidates = extract_candidates_from_results(results)
    assert len(candidates) == 1
    assert candidates[0].linkedin_url == "https://www.linkedin.com/in/test-user"


def test_deduplication_across_queries():
    results = [
        {"link": "https://www.linkedin.com/in/same-user/", "title": "A", "snippet": "s1", "position": 3, "query": "q1"},
        {"link": "https://www.linkedin.com/in/same-user", "title": "A", "snippet": "s2", "position": 1, "query": "q2"},
        {"link": "https://www.linkedin.com/in/same-user?utm=1", "title": "A", "snippet": "s3", "position": 5, "query": "q3"},
    ]
    candidates = extract_candidates_from_results(results)
    assert len(candidates) == 1
    assert len(candidates[0].found_in_queries) == 3
    assert candidates[0].best_position == 1
