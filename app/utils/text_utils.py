import re

_LINKEDIN_TITLE_SUFFIX = re.compile(r"\s*[|\-–—]\s*LinkedIn.*$", re.IGNORECASE)

_COUNTRY_NORMALIZE = {
    "us": "United States",
    "usa": "United States",
    "u.s.": "United States",
    "u.s.a.": "United States",
    "u.s.a": "United States",
    "united states": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "u.k": "United Kingdom",
    "united kingdom": "United Kingdom",
}

_COUNTRY_FROM_TEXT = (
    (re.compile(r"\b(united states of america|united states|u\.s\.a\.?|usa)\b", re.I), "United States"),
    (re.compile(r"\bus[-\s]?based\b", re.I), "United States"),
    (re.compile(r"\bgreen cards?\b", re.I), "United States"),
    (re.compile(r"\bu\.?s\.?\s+citizens?\b", re.I), "United States"),
    (re.compile(r"\bcanada\b", re.I), "Canada"),
    (re.compile(r"\bmexico\b", re.I), "Mexico"),
    (re.compile(r"\bindia\b", re.I), "India"),
    (re.compile(r"\b(united kingdom|u\.k\.)\b", re.I), "United Kingdom"),
)

_US_PRIMARY_RE = re.compile(
    r"\b(us[-\s]?based|united states|u\.s\.a\.?|\busa\b|green cards?|u\.?s\.?\s+citizens?|"
    r"location\s*:\s*(?:the\s+)?(?:usa|u\.s\.a\.?|u\.s\.|us)\b)",
    re.I,
)


def display_name_from_title(title: str) -> str:
    if not title:
        return "Unknown"
    cleaned = _LINKEDIN_TITLE_SUFFIX.sub("", title)
    for sep in [" | ", " – ", " — ", " - "]:
        if sep in cleaned:
            return cleaned.split(sep)[0].strip()
    return cleaned.strip() or "Unknown"


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def simplify_term(term: str, max_words: int = 3) -> str:
    """Keep search terms short so Google X-Ray queries stay effective."""
    cleaned = normalize_whitespace(term)
    if not cleaned:
        return ""
    words = cleaned.split()
    if len(words) <= max_words:
        return cleaned
    # Prefer product/core tokens over long descriptive phrases.
    return " ".join(words[:max_words])


def quote_phrase(term: str) -> str:
    """Quote multi-word phrases for X-Ray search queries."""
    cleaned = simplify_term(term)
    if not cleaned:
        return ""
    if " " in cleaned:
        return f'"{cleaned}"'
    return cleaned


def expand_locations(locations: list[str]) -> list[str]:
    """Split location strings into search terms and keep stated countries.

    'Texas, US' becomes Texas + United States. A JD that only says USA keeps
    United States instead of dropping the country as too broad.
    """
    expanded: list[str] = []
    for loc in locations:
        parts = [
            normalize_whitespace(p)
            for p in re.split(r"[,/|&]| and ", loc, flags=re.IGNORECASE)
            if p.strip()
        ]
        for part in parts:
            key = part.lower().rstrip(".")
            expanded.append(_COUNTRY_NORMALIZE.get(key, part))
    return list(dict.fromkeys(p for p in expanded if p))


def locations_from_jd_text(jd_text: str) -> list[str]:
    """Pull country names actually mentioned in the JD text."""
    found: list[str] = []
    for pattern, label in _COUNTRY_FROM_TEXT:
        if pattern.search(jd_text or ""):
            found.append(label)
    return list(dict.fromkeys(found))


def merge_jd_locations(extracted: list[str], jd_text: str) -> list[str]:
    """Keep extractor locations and add any countries the JD text clearly states."""
    merged = list(dict.fromkeys(expand_locations(extracted) + locations_from_jd_text(jd_text)))
    if _US_PRIMARY_RE.search(jd_text or ""):
        rest = [loc for loc in merged if loc.lower() not in {"united states", "usa", "us"}]
        merged = ["United States", *rest]
    return merged


def build_or_group(terms: list[str]) -> str:
    """Build an OR group like (\"A\" OR \"B\" OR C)."""
    quoted = [quote_phrase(t) for t in terms if t and t.strip()]
    unique = list(dict.fromkeys(q for q in quoted if q))
    if not unique:
        return ""
    if len(unique) == 1:
        return unique[0]
    return f"({' OR '.join(unique)})"
