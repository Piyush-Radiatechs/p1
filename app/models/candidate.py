from pydantic import BaseModel, Field


class Candidate(BaseModel):
    """Candidate discovered via search-engine metadata only — never scraped from LinkedIn."""

    linkedin_url: str
    title: str = ""
    snippet: str = ""
    best_position: int | None = None
    found_in_queries: list[str] = Field(default_factory=list)


class RankedCandidate(Candidate):
    match_score: int = 0
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
