from pydantic import BaseModel, Field


class ExperienceRange(BaseModel):
    min_years: int | None = None
    max_years: int | None = None


class JobRequirements(BaseModel):
    job_titles: list[str] = Field(default_factory=list)
    technical_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    experience: ExperienceRange = Field(default_factory=ExperienceRange)
    exclusions: list[str] = Field(default_factory=lambda: ["intern", "fresher"])
    industries: list[str] = Field(default_factory=list)
