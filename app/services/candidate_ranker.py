"""Lightweight candidate relevance scoring from search-engine metadata only.

COMPLIANCE: Scoring uses title, snippet, and query-repeat signals from SerpApi.
No LinkedIn profile pages are visited. The score is a sourcing signal, not a
hiring decision.
"""

from app.models.candidate import Candidate, RankedCandidate
from app.models.jd import JobRequirements


def _normalize(text: str) -> str:
    return text.lower()


def _skill_keywords(requirements: JobRequirements) -> list[str]:
    skills = requirements.technical_skills + requirements.preferred_skills
    return list(dict.fromkeys(s for s in skills if s.strip()))


def _skills_in_text(text: str, skills: list[str]) -> list[str]:
    normalized = _normalize(text)
    return [skill for skill in skills if _normalize(skill) in normalized]


def _title_skill_score(title: str, skills: list[str]) -> tuple[float, list[str]]:
    if not skills:
        return 0.0, []
    matched = _skills_in_text(title, skills)
    return len(matched) / len(skills), matched


def _snippet_skill_score(snippet: str, skills: list[str]) -> tuple[float, list[str]]:
    if not skills:
        return 0.0, []
    matched = _skills_in_text(snippet, skills)
    return len(matched) / len(skills), matched


def _repeat_query_score(found_in_queries: list[str], max_queries: int) -> float:
    if max_queries <= 0:
        return 0.0
    return min(len(found_in_queries) / max_queries, 1.0)


def rank_candidates(
    candidates: list[Candidate],
    requirements: JobRequirements,
    max_queries: int = 5,
) -> list[RankedCandidate]:
    """Score and rank candidates by search-metadata relevance to JD requirements."""
    skills = _skill_keywords(requirements)
    ranked: list[RankedCandidate] = []

    for candidate in candidates:
        title_ratio, title_matches = _title_skill_score(candidate.title, skills)
        snippet_ratio, snippet_matches = _snippet_skill_score(candidate.snippet, skills)
        repeat_ratio = _repeat_query_score(candidate.found_in_queries, max_queries)

        match_score = round(title_ratio * 40 + snippet_ratio * 40 + repeat_ratio * 20)
        matched_skills = list(dict.fromkeys(title_matches + snippet_matches))
        missing_skills = [s for s in skills if s not in matched_skills]

        ranked.append(
            RankedCandidate(
                **candidate.model_dump(),
                match_score=match_score,
                matched_skills=matched_skills,
                missing_skills=missing_skills,
            )
        )

    ranked.sort(key=lambda c: (-c.match_score, c.best_position or 999))
    return ranked
