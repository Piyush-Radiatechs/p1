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

_JUNIOR_TITLE_RE = re.compile(
    r"\b(intern(?:ship|ships|s)?|fresher|trainee|apprentice|entry[-\s]?level|"
    r"graduate (?:trainee|hire)|campus hire)\b",
    re.IGNORECASE,
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


def is_junior_profile_title(title: str) -> bool:
    """True when the search-result title is clearly an intern/fresher/entry role."""
    return bool(_JUNIOR_TITLE_RE.search(title or ""))


def extract_candidates_from_results(
    search_results: list[dict],
    *,
    drop_junior_titles: bool = False,
) -> list[Candidate]:
    """Filter search results to unique LinkedIn /in/ profile candidates."""
    by_url: dict[str, Candidate] = {}

    for result in search_results:
        link = result.get("link", "")
        normalized = normalize_linkedin_url(link)
        if not normalized:
            continue

        title = result.get("title") or ""
        if drop_junior_titles and is_junior_profile_title(title):
            continue

        query = result.get("query", "")
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
