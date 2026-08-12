"""Orchestrates the full JD → search → candidate discovery pipeline."""

import logging

from app.config import Settings, get_settings
from app.exceptions import AppError, QuotaExceededError
from app.services.candidate_extractor import extract_candidates_from_results
from app.services.jd_extractor import extract_job_requirements
from app.services.pdf_parser import extract_pdf_text
from app.services.query_generator import generate_xray_queries
from app.services.search_service import SearchProvider, SerpApiProvider

logger = logging.getLogger(__name__)


async def process_jd_pdf(
    pdf_bytes: bytes,
    filename: str = "upload.pdf",
    settings: Settings | None = None,
    search_provider: SearchProvider | None = None,
    serpapi_key: str | None = None,
) -> dict:
    """
    Full pipeline: PDF → Mistral → queries → SerpApi → LinkedIn URL extraction.

    COMPLIANCE: Only search-engine metadata is used. LinkedIn is never scraped.
    """
    settings = settings or get_settings()
    if serpapi_key and serpapi_key.strip():
        settings = settings.model_copy(update={"serpapi_key": serpapi_key.strip()})
    search_provider = search_provider or SerpApiProvider(settings)

    jd_text = extract_pdf_text(pdf_bytes)
    logger.info("Extracted %d characters from %s", len(jd_text), filename)

    requirements = await extract_job_requirements(jd_text, settings)
    queries = generate_xray_queries(requirements, max_queries=settings.max_queries_per_jd)

    search_results: list[dict] = []
    searches_run = 0

    try:
        for query in queries:
            results = await search_provider.search(query)
            searches_run += 1
            for result in results:
                search_results.append({**result, "query": query})
    except QuotaExceededError:
        raise
    except AppError:
        raise
    except Exception as exc:
        logger.exception("Unexpected search error")
        raise AppError(f"Search failed: {exc}", status_code=502) from exc

    candidates = extract_candidates_from_results(search_results)

    return {
        "filename": filename,
        "requirements": requirements.model_dump(),
        "queries": queries,
        "searches_run": searches_run,
        "search_results": search_results,
        "candidates_found": len(candidates),
        "candidates": [c.model_dump() for c in candidates],
    }
