"""Persist and load search history and candidate result tables."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import session_scope
from app.db.models import Search, SearchResult
from app.utils.text_utils import display_name_from_title


@dataclass(frozen=True)
class SearchSummary:
    id: int
    created_at: datetime
    source: str
    filename: str
    candidates_found: int
    job_titles: list[str]


def save_search(user_id: int, result: dict, *, source: str) -> int:
    """Store a completed search and its candidate rows. Returns the search id."""
    with session_scope() as session:
        search = Search(
            user_id=user_id,
            source=source,
            filename=(result.get("filename") or "")[:255],
            requirements=result.get("requirements") or {},
            queries=result.get("queries") or [],
            searches_run=int(result.get("searches_run") or 0),
            candidates_found=int(result.get("candidates_found") or 0),
            raw_results_count=len(result.get("search_results") or []),
        )
        session.add(search)
        session.flush()

        for index, candidate in enumerate(result.get("candidates") or []):
            title = candidate.get("title") or ""
            session.add(
                SearchResult(
                    search_id=search.id,
                    display_order=index,
                    name_title=display_name_from_title(title)[:255],
                    search_title=title[:512],
                    linkedin_url=(candidate.get("linkedin_url") or "")[:512],
                    snippet=candidate.get("snippet") or "",
                    found_in_queries=list(candidate.get("found_in_queries") or []),
                )
            )
        return search.id


def list_searches(user_id: int, *, limit: int = 50) -> list[SearchSummary]:
    with session_scope() as session:
        rows = session.scalars(
            select(Search)
            .where(Search.user_id == user_id)
            .order_by(Search.created_at.desc())
            .limit(limit)
        ).all()
        summaries: list[SearchSummary] = []
        for search in rows:
            requirements = search.requirements or {}
            summaries.append(
                SearchSummary(
                    id=search.id,
                    created_at=search.created_at,
                    source=search.source,
                    filename=search.filename,
                    candidates_found=search.candidates_found,
                    job_titles=list(requirements.get("job_titles") or []),
                )
            )
        return summaries


def load_search(user_id: int, search_id: int) -> dict | None:
    with session_scope() as session:
        search = session.scalar(
            select(Search)
            .options(selectinload(Search.results))
            .where(Search.id == search_id, Search.user_id == user_id)
        )
        if search is None:
            return None
        return _search_to_result(search)


def _search_to_result(search: Search) -> dict:
    candidates = []
    for row in search.results:
        candidates.append(
            {
                "linkedin_url": row.linkedin_url,
                "title": row.search_title,
                "snippet": row.snippet,
                "found_in_queries": list(row.found_in_queries or []),
            }
        )
    return {
        "filename": search.filename,
        "requirements": search.requirements or {},
        "queries": search.queries or [],
        "searches_run": search.searches_run,
        "search_results": [],
        "raw_results_count": search.raw_results_count,
        "candidates_found": search.candidates_found,
        "candidates": candidates,
    }
