"""Deterministic X-Ray query builder for LinkedIn profile discovery via Google.

COMPLIANCE: Queries target public search-engine results only. This module does
not access LinkedIn directly — it generates site:linkedin.com/in/ X-Ray queries
for use with SerpApi/Google.
"""

from app.models.jd import JobRequirements
from app.utils.text_utils import (
    build_or_group,
    expand_locations,
    normalize_whitespace,
    quote_phrase,
    simplify_term,
)

LINKEDIN_XRAY_SITE = "site:linkedin.com/in/"


def _build_exclusions(exclusions: list[str]) -> list[str]:
    terms = exclusions or ["intern", "fresher"]
    # Keep exclusions short; too many negatives can zero out Google results.
    cleaned = []
    for term in terms:
        simple = simplify_term(term, max_words=2).lower()
        if simple:
            cleaned.append(f"-{simple}")
    return list(dict.fromkeys(cleaned))[:3]


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
    exclusions = _build_exclusions(requirements.exclusions)

    title_group = build_or_group(titles[:4])
    location_group = build_or_group(locations[:4])
    # Prefer short skill tokens for better Google hit rates.
    core_skill_group = build_or_group(core_skills[:3])
    primary_skill = quote_phrase(core_skills[0]) if core_skills else ""
    all_skills = list(dict.fromkeys(core_skills + preferred))
    skill_group = build_or_group(all_skills[:4])

    queries: list[str] = []

    # Query 1: Title + primary skill + location (broader, higher hit rate)
    queries.append(
        _join_query_parts(
            [LINKEDIN_XRAY_SITE, title_group, primary_skill, location_group, *exclusions]
        )
    )

    # Query 2: Title + core skills + location
    queries.append(
        _join_query_parts(
            [LINKEDIN_XRAY_SITE, title_group, core_skill_group, location_group, *exclusions]
        )
    )

    # Query 3: Skill-heavy (no title emphasis)
    queries.append(
        _join_query_parts(
            [LINKEDIN_XRAY_SITE, skill_group, location_group, *exclusions]
        )
    )

    # Query 4: Alternate titles
    if len(titles) > 1:
        alt_title = build_or_group(titles[1:4])
        queries.append(
            _join_query_parts(
                [LINKEDIN_XRAY_SITE, alt_title, primary_skill, location_group, *exclusions]
            )
        )

    # Query 5+: Single-location variants (broader than stacking all locations)
    if locations:
        for loc in locations[:2]:
            queries.append(
                _join_query_parts(
                    [
                        LINKEDIN_XRAY_SITE,
                        title_group,
                        primary_skill,
                        quote_phrase(loc),
                        *exclusions,
                    ]
                )
            )

    # Broader fallback: title + location only
    if title_group and location_group:
        queries.append(
            _join_query_parts(
                [LINKEDIN_XRAY_SITE, title_group, location_group, *exclusions]
            )
        )

    return _dedupe_queries(queries)[:max_queries]
