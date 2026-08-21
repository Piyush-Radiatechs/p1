"""Deterministic X-Ray query builder for LinkedIn profile discovery via Google.

COMPLIANCE: Queries target public search-engine results only. This module does
not access LinkedIn directly — it generates site:linkedin.com/in/ X-Ray queries
for use with SerpApi/Google.
"""

from app.models.jd import ExperienceRange, JobRequirements
from app.utils.text_utils import (
    build_or_group,
    expand_locations,
    normalize_whitespace,
    quote_phrase,
    simplify_term,
)

LINKEDIN_XRAY_SITE = "site:linkedin.com/in/"

_JUNIOR_EXCLUSIONS = ("intern", "internship", "fresher", "entry-level", "trainee")


def _build_exclusions(exclusions: list[str], min_years: int | None) -> list[str]:
    terms = list(exclusions or [])
    if min_years is not None and min_years >= 3:
        terms.extend(_JUNIOR_EXCLUSIONS)
    if not terms:
        terms = ["intern", "fresher"]
    cleaned: list[str] = []
    for term in terms:
        simple = simplify_term(term, max_words=2).lower()
        if not simple:
            continue
        token = f'-"{simple}"' if " " in simple else f"-{simple}"
        cleaned.append(token)
    # Keep a few negatives; too many can zero out Google results.
    return list(dict.fromkeys(cleaned))[:5]


def _seniority_group(experience: ExperienceRange | None) -> str:
    min_years = experience.min_years if experience else None
    if min_years is None or min_years < 5:
        return ""
    terms = ["Senior", "Lead"]
    if min_years >= 8:
        terms.append("SME")
    return build_or_group(terms)


def _join_query_parts(parts: list[str]) -> str:
    cleaned = [normalize_whitespace(p) for p in parts if p and p.strip()]
    return normalize_whitespace(" ".join(cleaned))


def _dedupe_queries(queries: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for query in queries:
        normalized = normalize_whitespace(query)
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def generate_xray_queries(
    requirements: JobRequirements,
    max_queries: int = 5,
) -> list[str]:
    """Generate up to max_queries LinkedIn X-Ray search variants."""
    titles = [simplify_term(t) for t in requirements.job_titles if t.strip()]
    titles = list(dict.fromkeys(t for t in titles if t))

    core_skills = [simplify_term(s) for s in requirements.technical_skills if s.strip()]
    core_skills = list(dict.fromkeys(s for s in core_skills if s))

    preferred = [simplify_term(s) for s in requirements.preferred_skills if s.strip()]
    preferred = list(dict.fromkeys(s for s in preferred if s))

    locations = expand_locations(requirements.locations)
    min_years = requirements.experience.min_years if requirements.experience else None
    exclusions = _build_exclusions(requirements.exclusions, min_years)
    seniority = _seniority_group(requirements.experience)

    title_group = build_or_group(titles[:4])
    location_group = build_or_group(locations[:6])
    primary_location = quote_phrase(locations[0]) if locations else ""
    # Prefer short skill tokens for better Google hit rates.
    core_skill_group = build_or_group(core_skills[:3])
    primary_skill = quote_phrase(core_skills[0]) if core_skills else ""
    all_skills = list(dict.fromkeys(core_skills + preferred))
    skill_group = build_or_group(all_skills[:4])

    queries: list[str] = []

    # Query 1: Title + seniority + primary skill + all JD locations
    queries.append(
        _join_query_parts(
            [
                LINKEDIN_XRAY_SITE,
                title_group,
                seniority,
                primary_skill,
                location_group,
                *exclusions,
            ]
        )
    )

    # Query 2: Title + core skills + all locations (no seniority, higher recall)
    queries.append(
        _join_query_parts(
            [LINKEDIN_XRAY_SITE, title_group, core_skill_group, location_group, *exclusions]
        )
    )

    # Query 3: Skill-heavy, pinned to the primary work location
    queries.append(
        _join_query_parts(
            [LINKEDIN_XRAY_SITE, skill_group, primary_location or location_group, *exclusions]
        )
    )

    # Query 4: Alternate titles + primary location
    if len(titles) > 1:
        alt_title = build_or_group(titles[1:4])
        queries.append(
            _join_query_parts(
                [
                    LINKEDIN_XRAY_SITE,
                    alt_title,
                    seniority,
                    primary_skill,
                    primary_location or location_group,
                    *exclusions,
                ]
            )
        )

    # Query 5+: Remaining single-location variants, primary location first
    if locations:
        for loc in locations[:3]:
            queries.append(
                _join_query_parts(
                    [
                        LINKEDIN_XRAY_SITE,
                        title_group,
                        seniority,
                        primary_skill,
                        quote_phrase(loc),
                        *exclusions,
                    ]
                )
            )

    # Broader fallback: title + all locations
    if title_group and location_group:
        queries.append(
            _join_query_parts(
                [LINKEDIN_XRAY_SITE, title_group, location_group, *exclusions]
            )
        )

    return _dedupe_queries(queries)[:max_queries]
