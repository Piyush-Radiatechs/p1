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
    # Keep up to 3 high-impact negative tokens so Google does not penalize or zero out results
    return list(dict.fromkeys(cleaned))[:3]


def _seniority_group(experience: ExperienceRange | None) -> str:
    min_years = experience.min_years if experience else None
    if min_years is None or min_years < 4:
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
    """Generate up to max_queries distinct, recruiter-grade LinkedIn X-Ray queries."""
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

    title_group = build_or_group(titles[:3]) if titles else ""
    alt_titles = titles[1:4] if len(titles) > 1 else titles[:2]
    alt_title_group = build_or_group(alt_titles) if alt_titles else title_group

    primary_title = quote_phrase(titles[0]) if titles else ""
    primary_skill = quote_phrase(core_skills[0]) if core_skills else ""

    # Locations: Separate target local/state regions from broad country names
    target_locations = [
        loc
        for loc in locations
        if loc.lower() not in {"united states", "usa", "us", "india", "united kingdom", "uk", "canada", "mexico"}
    ]
    target_loc_group = build_or_group(target_locations[:3]) if target_locations else build_or_group(locations[:3])
    all_loc_group = build_or_group(locations[:4]) if locations else ""

    sec_skills = core_skills[1:4]
    sec_skill_group = build_or_group(sec_skills) if sec_skills else ""

    niche_pool = core_skills[2:6] + preferred[:3]
    niche_pool = list(dict.fromkeys(s for s in niche_pool if s and s != primary_skill))
    niche_skill_group = build_or_group(niche_pool[:3]) if niche_pool else ""

    queries: list[str] = []

    # 1. High Precision: Target Titles + Seniority + Primary Skill + Targeted Location
    queries.append(
        _join_query_parts(
            [LINKEDIN_XRAY_SITE, title_group, seniority, primary_skill, target_loc_group or all_loc_group, *exclusions]
        )
    )

    # 2. Tech Stack Specialist: Title Group + Primary Skill + Secondary Core Skills + Targeted Location
    queries.append(
        _join_query_parts(
            [LINKEDIN_XRAY_SITE, title_group, primary_skill, sec_skill_group, target_loc_group or all_loc_group, *exclusions]
        )
    )

    # 3. Alternative & Synonymous Titles: Alternative Titles + Primary Skill + All Locations (Broader)
    queries.append(
        _join_query_parts(
            [LINKEDIN_XRAY_SITE, alt_title_group or title_group, primary_skill, all_loc_group, *exclusions]
        )
    )

    # 4. Niche & Ecosystem Skills: Primary Title + Primary Skill + Niche Skills + Targeted Location
    queries.append(
        _join_query_parts(
            [
                LINKEDIN_XRAY_SITE,
                primary_title,
                primary_skill,
                niche_skill_group or sec_skill_group,
                target_loc_group or all_loc_group,
                *exclusions,
            ]
        )
    )

    # 5. High Recall Safety Net: Primary Title OR Primary Skill + All Locations
    if primary_title and primary_skill:
        broad_identifier = f"({primary_title} OR {primary_skill})"
    else:
        broad_identifier = primary_title or primary_skill or title_group

    queries.append(
        _join_query_parts(
            [LINKEDIN_XRAY_SITE, broad_identifier, all_loc_group, *exclusions]
        )
    )

    # Fallbacks if locations have multiple individual cities/regions
    if locations and len(queries) < max_queries:
        for loc in locations[:3]:
            queries.append(
                _join_query_parts(
                    [LINKEDIN_XRAY_SITE, title_group, primary_skill, quote_phrase(loc), *exclusions]
                )
            )

    return _dedupe_queries(queries)[:max_queries]
