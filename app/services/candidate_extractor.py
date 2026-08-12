"""Extract LinkedIn profile URLs from search-engine results.

COMPLIANCE BOUNDARY:
- Only URLs matching linkedin.com/in/... are kept.
- Company, jobs, posts, and school URLs are rejected.
- We do NOT visit, scrape, or automate LinkedIn profile pages.
- The recruiter manually opens discovered profile URLs.
"""

import re
from urllib.parse import urlparse, urlunparse

from app.models.candidate import Candidate

LINKEDIN_PROFILE_PATTERN = re.compile(
    r"^https?://(?:[a-z]{2,3}\.)?linkedin\.com/in/[^/?#]+/?",
    re.IGNORECASE,
)

EXCLUDED_PATH_PREFIXES = (
    "/company/",
    "/jobs/",
    "/posts/",
    "/school/",
    "/pub/",
    "/groups/",
)


def normalize_linkedin_url(url: str) -> str | None:
    """Normalize a LinkedIn profile URL or return None if not a valid /in/ profile."""
    if not url or not url.strip():
        return None

    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").lower()
    if "linkedin.com" not in host:
        return None

    path = parsed.path or ""
    path_lower = path.lower()

    for prefix in EXCLUDED_PATH_PREFIXES:
        if path_lower.startswith(prefix):
            return None

    if not path_lower.startswith("/in/"):
        return None

    if not LINKEDIN_PROFILE_PATTERN.match(url.strip()):
        return None

    # Remove trailing slash and query parameters
    clean_path = path.rstrip("/") or path
    normalized = urlunparse(
        (
            "https",
            "www.linkedin.com",
            clean_path,
            "",
            "",
            "",
        )
    )
    return normalized


def is_linkedin_profile_url(url: str) -> bool:
    return normalize_linkedin_url(url) is not None


def extract_candidates_from_results(
    search_results: list[dict],
) -> list[Candidate]:
    """Filter search results to unique LinkedIn /in/ profile candidates."""
    by_url: dict[str, Candidate] = {}

    for result in search_results:
        link = result.get("link", "")
        normalized = normalize_linkedin_url(link)
        if not normalized:
            continue

        query = result.get("query", "")
        title = result.get("title") or ""
        snippet = result.get("snippet") or ""
        position = result.get("position")

        if normalized in by_url:
            existing = by_url[normalized]
            if query and query not in existing.found_in_queries:
                existing.found_in_queries.append(query)
            if position is not None and (
                existing.best_position is None or position < existing.best_position
            ):
                existing.best_position = position
            if not existing.title and title:
                existing.title = title
            if not existing.snippet and snippet:
                existing.snippet = snippet
        else:
            by_url[normalized] = Candidate(
                linkedin_url=normalized,
                title=title,
                snippet=snippet,
                best_position=position,
                found_in_queries=[query] if query else [],
            )

    return list(by_url.values())
