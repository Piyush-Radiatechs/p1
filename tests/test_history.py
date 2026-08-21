"""Unit tests for search history and result table persistence."""

from app.services.auth_service import register_user
from app.services.history_service import list_searches, load_search, save_search

SAMPLE_RESULT = {
    "filename": "windchill_jd.pdf",
    "requirements": {
        "job_titles": ["Windchill Developer"],
        "technical_skills": ["Java"],
        "locations": ["Texas"],
    },
    "queries": ['site:linkedin.com/in/ "Windchill Developer"'],
    "searches_run": 1,
    "search_results": [{"title": "raw", "link": "https://example.com"}],
    "candidates_found": 1,
    "candidates": [
        {
            "linkedin_url": "https://www.linkedin.com/in/windchill-dev",
            "title": "Windchill PLM Consultant - Java | LinkedIn",
            "snippet": "Experienced Windchill developer in Texas.",
            "found_in_queries": ['site:linkedin.com/in/ "Windchill Developer"'],
        }
    ],
}


def test_save_and_load_search_history(db):
    user = register_user("recruiter1", "secret123")
    search_id = save_search(user.id, SAMPLE_RESULT, source="file")

    summaries = list_searches(user.id)
    assert len(summaries) == 1
    assert summaries[0].id == search_id
    assert summaries[0].filename == "windchill_jd.pdf"
    assert summaries[0].candidates_found == 1
    assert "Windchill Developer" in summaries[0].job_titles

    loaded = load_search(user.id, search_id)
    assert loaded is not None
    assert loaded["filename"] == "windchill_jd.pdf"
    assert loaded["raw_results_count"] == 1
    assert loaded["candidates"][0]["linkedin_url"] == "https://www.linkedin.com/in/windchill-dev"
    assert loaded["candidates"][0]["title"].startswith("Windchill PLM Consultant")


def test_load_search_is_scoped_to_user(db):
    owner = register_user("owner", "secret123")
    other = register_user("other", "secret123")
    search_id = save_search(owner.id, SAMPLE_RESULT, source="text")

    assert load_search(other.id, search_id) is None
    assert list_searches(other.id) == []
