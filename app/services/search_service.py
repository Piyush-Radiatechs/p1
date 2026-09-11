"""Search provider abstraction and SerpApi implementation.

COMPLIANCE: Search results come from Google via SerpApi. We only inspect returned
search metadata (title, link, snippet). No LinkedIn pages are fetched or scraped.
"""

import asyncio
import logging
from abc import ABC, abstractmethod

import httpx

from app.config import Settings, get_settings
from app.exceptions import QuotaExceededError, SearchError

logger = logging.getLogger(__name__)

SERPAPI_URL = "https://serpapi.com/search.json"

# SerpApi sometimes returns this as an "error" when Google simply has no hits.
_EMPTY_RESULT_MARKERS = (
    "hasn't returned any results",
    "has not returned any results",
    "no results",
)


def _is_empty_results_message(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _EMPTY_RESULT_MARKERS)


class SearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str) -> list[dict]:
        """Return normalized organic search results."""


class SerpApiProvider(SearchProvider):
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()

    async def search(self, query: str) -> list[dict]:
        if not self.settings.serpapi_configured:
            raise SearchError("SERPAPI_KEY is not configured.")

        params = {
            "engine": "google",
            "q": query,
            "api_key": self.settings.serpapi_key,
            "num": self.settings.max_results_per_query,
            "google_domain": self.settings.google_domain,
            "gl": self.settings.google_gl,
            "hl": self.settings.google_hl,
        }

        timeout = httpx.Timeout(60.0, connect=20.0)
        last_timeout: httpx.TimeoutException | None = None
        response = None
        for attempt in range(1, 4):
            try:
                # Avoid logging full request URLs (they include the API key).
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get(SERPAPI_URL, params=params)
                break
            except httpx.TimeoutException as exc:
                last_timeout = exc
                logger.warning("SerpApi timed out on attempt %s/3", attempt)
                if attempt < 3:
                    await asyncio.sleep(1.5 * attempt)
            except httpx.RequestError as exc:
                raise SearchError(f"SerpApi network error: {exc}") from exc
        else:
            raise SearchError("SerpApi request timed out.") from last_timeout

        if response is None:
            raise SearchError("SerpApi request timed out.") from last_timeout

        if response.status_code == 429:
            raise QuotaExceededError()

        if response.status_code >= 400:
            body = response.text
            logger.error("SerpApi HTTP error %s", response.status_code)
            if "quota" in body.lower() or "rate limit" in body.lower():
                raise QuotaExceededError()
            raise SearchError(f"SerpApi returned status {response.status_code}.")

        try:
            data = response.json()
        except ValueError as exc:
            raise SearchError("SerpApi returned invalid JSON.") from exc

        if "error" in data:
            error_msg = str(data["error"])
            if _is_empty_results_message(error_msg):
                logger.info("SerpApi returned no organic results for a query; continuing.")
                return []
            if "quota" in error_msg.lower() or "limit" in error_msg.lower():
                raise QuotaExceededError(error_msg)
            raise SearchError(f"SerpApi error: {error_msg}")

        organic = data.get("organic_results") or []
        results: list[dict] = []
        for item in organic:
            results.append(
                {
                    "position": item.get("position"),
                    "title": item.get("title") or "",
                    "link": item.get("link") or "",
                    "snippet": item.get("snippet") or "",
                }
            )
        return results


async def run_searches(
    queries: list[str],
    provider: SearchProvider | None = None,
) -> list[dict]:
    """Run multiple queries and return aggregated search metadata."""
    provider = provider or SerpApiProvider()
    all_results: list[dict] = []

    for query in queries:
        results = await provider.search(query)
        for result in results:
            all_results.append({**result, "query": query})

    return all_results
