"""Integration tests for the search pipeline with mocked providers."""

from unittest.mock import AsyncMock, patch

import fitz
import pytest

from app.models.jd import ExperienceRange, JobRequirements
from app.services.pipeline import process_jd_pdf
from app.services.search_service import SearchProvider


def _make_windchill_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    text = (
        "Windchill Developer / PLM Developer. Location: Texas, Dallas. "
        "3-8 years experience. Skills: Windchill, PDMLink, Java, OIR."
    )
    page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


MOCK_REQUIREMENTS = JobRequirements(
    job_titles=["Windchill Developer", "PLM Developer"],
    technical_skills=["Windchill", "PDMLink", "Java"],
    preferred_skills=["OIR"],
    locations=["Texas", "Dallas"],
    experience=ExperienceRange(min_years=3, max_years=8),
)


class MockSearchProvider(SearchProvider):
    async def search(self, query: str) -> list[dict]:
        return [
            {
                "position": 1,
                "title": "Windchill PLM Consultant - Java",
                "link": "https://www.linkedin.com/in/windchill-dev",
                "snippet": "Experienced Windchill and PDMLink developer in Texas.",
            },
            {
                "position": 2,
                "title": "Example Company",
                "link": "https://www.linkedin.com/company/example",
                "snippet": "Not a profile.",
            },
        ]


@pytest.mark.asyncio
async def test_pipeline_with_mocks():
    pdf_bytes = _make_windchill_pdf()
    mock_provider = MockSearchProvider()

    with patch(
        "app.services.pipeline.extract_job_requirements",
        new=AsyncMock(return_value=MOCK_REQUIREMENTS),
    ):
        result = await process_jd_pdf(
            pdf_bytes,
            filename="windchill_jd.pdf",
            search_provider=mock_provider,
        )

    assert result["filename"] == "windchill_jd.pdf"
    assert "Windchill Developer" in result["requirements"]["job_titles"]
    assert all("site:linkedin.com/in/" in q for q in result["queries"])
    assert result["searches_run"] == len(result["queries"])
    assert result["candidates_found"] == 1
    assert result["candidates"][0]["linkedin_url"] == "https://www.linkedin.com/in/windchill-dev"
    assert len(result["search_results"]) == 2 * result["searches_run"]
