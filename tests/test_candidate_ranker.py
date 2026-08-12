"""Unit tests for candidate relevance scoring."""

from app.models.candidate import Candidate
from app.models.jd import JobRequirements
from app.services.candidate_ranker import rank_candidates


REQUIREMENTS = JobRequirements(
    job_titles=["Windchill Developer"],
    technical_skills=["Windchill", "PDMLink", "Java"],
    preferred_skills=["OIR"],
)


def test_strong_candidate_scores_higher():
    strong = Candidate(
        linkedin_url="https://www.linkedin.com/in/strong",
        title="Windchill PLM Developer - Java PDMLink",
        snippet="Expert in Windchill, PDMLink, Java, and OIR workflows.",
        found_in_queries=["q1", "q2", "q3"],
    )
    weak = Candidate(
        linkedin_url="https://www.linkedin.com/in/weak",
        title="Software Engineer",
        snippet="General developer with some Java experience.",
        found_in_queries=["q1"],
    )

    ranked = rank_candidates([weak, strong], REQUIREMENTS, max_queries=3)

    assert ranked[0].linkedin_url == strong.linkedin_url
    assert ranked[0].match_score > ranked[1].match_score
    assert "Windchill" in ranked[0].matched_skills
    assert "Windchill" in ranked[0].matched_skills


def test_missing_skills_reported():
    candidate = Candidate(
        linkedin_url="https://www.linkedin.com/in/partial",
        title="Java Developer",
        snippet="Java backend engineer.",
        found_in_queries=["q1"],
    )
    ranked = rank_candidates([candidate], REQUIREMENTS, max_queries=1)
    assert "Java" in ranked[0].matched_skills
    assert "Windchill" in ranked[0].missing_skills
