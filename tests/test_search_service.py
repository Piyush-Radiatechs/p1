"""Unit tests for SerpApi empty-result handling."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.config import Settings
from app.services.search_service import SerpApiProvider


@pytest.mark.asyncio
async def test_empty_google_results_returns_empty_list():
    settings = Settings(serpapi_key="test-key")
    provider = SerpApiProvider(settings)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "error": "Google hasn't returned any results for this query."
    }

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.return_value = mock_response

    with patch("app.services.search_service.httpx.AsyncClient", return_value=mock_client):
        results = await provider.search('site:linkedin.com/in/ "Windchill Developer"')

    assert results == []


@pytest.mark.asyncio
async def test_timeout_is_retried_then_succeeds():
    settings = Settings(serpapi_key="test-key")
    provider = SerpApiProvider(settings)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"organic_results": []}

    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.get.side_effect = [httpx.TimeoutException("slow"), mock_response]

    with (
        patch("app.services.search_service.httpx.AsyncClient", return_value=mock_client),
        patch("app.services.search_service.asyncio.sleep", new=AsyncMock()),
    ):
        results = await provider.search("site:linkedin.com/in/ test")

    assert results == []
    assert mock_client.get.call_count == 2
