import re

_COUNTRY_ONLY = {"us", "usa", "u.s.", "u.s.a.", "united states", "india", "uk", "u.k."}


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
    """Split 'Texas, US' into usable place names; drop country-only tokens."""
    expanded: list[str] = []
    for loc in locations:
        parts = [normalize_whitespace(p) for p in re.split(r"[,/|]", loc) if p.strip()]
        for part in parts:
            if part.lower() in _COUNTRY_ONLY:
                continue
            expanded.append(part)
    return list(dict.fromkeys(expanded))


def build_or_group(terms: list[str]) -> str:
    """Build an OR group like (\"A\" OR \"B\" OR C)."""
    quoted = [quote_phrase(t) for t in terms if t and t.strip()]
    unique = list(dict.fromkeys(q for q in quoted if q))
    if not unique:
        return ""
    if len(unique) == 1:
        return unique[0]
    return f"({' OR '.join(unique)})"
