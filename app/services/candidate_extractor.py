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

_NON_CANDIDATE_TITLE_RE = re.compile(
    r"\b(talent acquisition|recruiter|headhunter|staffing|sourcer|hr manager|human resources|"
    r"chief executive officer|\bceo\b|founder|co-founder|managing partner|sales director|"
    r"account executive|business development manager|\bbdm\b)\b",
    re.IGNORECASE,
)

_NON_US_SUBDOMAINS = frozenset(
    {
        "in", "uk", "ca", "au", "pk", "ae", "sg", "de", "fr", "nl", "es", "it", "br", "mx",
        "ph", "za", "ng", "sa", "nz", "ie", "se", "ch", "pl", "be", "at", "dk", "no", "fi",
        "hk", "my", "id", "eg", "ke", "gh", "vn", "th", "jp", "kr", "cn", "tw", "tr", "gr",
    }
)

_US_STATES = frozenset(
    {
        "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut",
        "delaware", "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa",
        "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan",
        "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada", "new hampshire",
        "new jersey", "new mexico", "new york", "north carolina", "north dakota", "ohio",
        "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina", "south dakota",
        "tennessee", "texas", "utah", "vermont", "virginia", "washington", "west virginia",
        "wisconsin", "wyoming", "district of columbia",
    }
)

_US_STATE_CODES = frozenset(
    {
        "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id", "il", "in",
        "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv",
        "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc", "sd", "tn",
        "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy", "dc",
    }
)

_COUNTRY_ONLY = frozenset(
    {
        "united states",
        "usa",
        "us",
        "u.s.",
        "u.s.a.",
        "india",
        "united kingdom",
        "uk",
        "canada",
        "mexico",
        "australia",
    }
)

_US_LOCATION_MARKER_RE = re.compile(
    r"(?:location:\s*united states|,\s*united states|\bunited states\b|\bu\.s\.a\.?|\busa\b|"
    r"location\s*:\s*the\s+united\s+states|"
    r',\s*(?:al|ak|az|ar|ca|co|ct|de|fl|ga|hi|id|il|in|ia|ks|ky|la|me|md|ma|mi|mn|ms|mo|mt|'
    r'ne|nv|nh|nj|nm|ny|nc|nd|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|vt|va|wa|wv|wi|wy|dc)\b)',
    re.IGNORECASE,
)

_OFFSHORE_PRIMARY_RE = re.compile(
    r"\b(?:chennai|tamil nadu|bengaluru|bangalore|pune|mumbai|noida|gurgaon|gurugram|delhi|"
    r"kolkata|hyderabad|ahmedabad|jaipur|coimbatore|kerala|karnataka|telangana|"
    r"andhra pradesh|maharashtra|secunderabad|lahore|karachi|islamabad|"
    r"manila|bangkok|jakarta|ho chi minh)\b",
    re.IGNORECASE,
)


def is_us_target_location(locations: list[str] | None) -> bool:
    """True if the JD targets US / United States candidates."""
    if not locations:
        return False
    for loc in locations:
        cleaned = (loc or "").strip().lower()
        if cleaned in {"united states", "usa", "us", "u.s.", "u.s.a.", "us only", "usa only"}:
            return True
        if cleaned in _US_STATES or cleaned in _US_STATE_CODES:
            return True
        if "united states" in cleaned or "usa" in cleaned or "us based" in cleaned:
            return True
    return False


def _locality_tokens(locations: list[str] | None) -> list[str]:
    """Cities/regions from the JD (e.g. Denver), excluding country-only tokens."""
    tokens: list[str] = []
    for loc in locations or []:
        cleaned = (loc or "").strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in _COUNTRY_ONLY or key in _US_STATES:
            continue
        tokens.append(cleaned)
    return list(dict.fromkeys(tokens))


def is_non_candidate_profile_title(title: str) -> bool:
    """True when the search-result title is a recruiter, HR, or executive role."""
    return bool(_NON_CANDIDATE_TITLE_RE.search(title or ""))


def _linkedin_subdomain(url: str) -> str:
    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").lower()
    return host.split(".")[0] if "." in host else ""


def _has_us_evidence(combined: str, locality_tokens: list[str]) -> bool:
    if _US_LOCATION_MARKER_RE.search(combined):
        return True
    if any(re.search(rf"\b{re.escape(state)}\b", combined, re.IGNORECASE) for state in _US_STATES):
        return True
    for token in locality_tokens:
        if re.search(rf"\b{re.escape(token)}\b", combined, re.IGNORECASE):
            return True
    return False


def _is_clear_offshore_profile(combined: str) -> bool:
    """Reject when snippet clearly places the person offshore without a US override."""
    if not _OFFSHORE_PRIMARY_RE.search(combined):
        return False
    if re.search(
        r"(?:location:\s*united states|,\s*(?:[A-Za-z\s]+,\s*)?united states|\bunited states\b)",
        combined,
        re.IGNORECASE,
    ):
        return False
    if any(
        re.search(rf"\b{re.escape(state)}\b", combined, re.IGNORECASE) for state in _US_STATES
    ):
        return False
    return True


def passes_us_location_filter(
    url: str,
    title: str,
    snippet: str,
    target_locations: list[str] | None,
) -> bool:
    """Filter US-target JDs without requiring every Google snippet to say 'United States'.

    Rejects obvious non-US profiles; keeps US-confirmed and location-ambiguous hits.
    """
    if not url:
        return False

    subdomain = _linkedin_subdomain(url)
    if subdomain in _NON_US_SUBDOMAINS:
        return False

    combined = f"{title} {snippet}".strip()
    locality_tokens = _locality_tokens(target_locations)

    if _is_clear_offshore_profile(combined):
        return False

    if _has_us_evidence(combined, locality_tokens):
        return True

    # Google often omits location in the title/snippet — keep www profiles unless offshore.
    if subdomain in {"", "www"} and not _OFFSHORE_PRIMARY_RE.search(combined):
        return True

    return False


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

    clean_path = path.rstrip("/") or path
    return urlunparse(("https", "www.linkedin.com", clean_path, "", "", ""))


def is_linkedin_profile_url(url: str) -> bool:
    return normalize_linkedin_url(url) is not None


def is_junior_profile_title(title: str) -> bool:
    """True when the search-result title is clearly an intern/fresher/entry role."""
    return bool(_JUNIOR_TITLE_RE.search(title or ""))


def extract_candidates_from_results(
    search_results: list[dict],
    *,
    drop_junior_titles: bool = False,
    target_locations: list[str] | None = None,
    strict_location: bool = True,
    drop_non_candidates: bool = True,
) -> list[Candidate]:
    """Filter search results to unique LinkedIn /in/ profile candidates."""
    by_url: dict[str, Candidate] = {}
    filter_us = is_us_target_location(target_locations) if strict_location else False

    for result in search_results:
        link = result.get("link", "")
        normalized = normalize_linkedin_url(link)
        if not normalized:
            continue

        title = result.get("title") or ""
        snippet = result.get("snippet") or ""

        if drop_non_candidates and is_non_candidate_profile_title(title):
            continue

        if drop_junior_titles and is_junior_profile_title(title):
            continue

        if filter_us and not passes_us_location_filter(link, title, snippet, target_locations):
            continue

        query = result.get("query", "")
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
