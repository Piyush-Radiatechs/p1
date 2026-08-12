"""Mistral-powered JD requirement extraction.

COMPLIANCE: This service only parses job-description text. It does not access
LinkedIn or any candidate profile data.
"""

import json
import logging
import re

import httpx

from app.config import Settings, get_settings
from app.exceptions import JDExtractionError
from app.models.jd import JobRequirements

logger = logging.getLogger(__name__)

MISTRAL_CHAT_URL = "https://api.mistral.ai/v1/chat/completions"

SYSTEM_PROMPT = """You are a recruitment analyst. Extract structured job requirements from a job description.

Rules:
- Extract ONLY requirements explicitly stated or clearly implied in the JD.
- Never invent skills, titles, locations, or experience that are not supported by the text.
- Identify realistic job-title variants based on the role described.
- Separate must-have technical skills from preferred/nice-to-have skills.
- Extract location requirements (city, state, region, remote/hybrid if stated).
- Extract experience range in years when mentioned.
- Include common exclusion terms such as intern/fresher when the JD targets experienced hires.
- Return machine-readable JSON only — no markdown, no commentary.

JSON schema:
{
  "job_titles": ["string"],
  "technical_skills": ["string"],
  "preferred_skills": ["string"],
  "locations": ["string"],
  "experience": {"min_years": int|null, "max_years": int|null},
  "exclusions": ["string"],
  "industries": ["string"]
}"""


def _strip_json_fence(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


async def extract_job_requirements(
    jd_text: str,
    settings: Settings | None = None,
) -> JobRequirements:
    """Convert raw JD text into a validated JobRequirements model via Mistral."""
    settings = settings or get_settings()

    if not settings.mistral_configured:
        raise JDExtractionError("MISTRAL_API_KEY is not configured.")

    if not jd_text.strip():
        raise JDExtractionError("Job description text is empty.")

    payload = {
        "model": settings.mistral_model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": jd_text[:120_000]},
        ],
    }

    headers = {
        "Authorization": f"Bearer {settings.mistral_api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(MISTRAL_CHAT_URL, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise JDExtractionError("Mistral API request timed out.") from exc
    except httpx.RequestError as exc:
        raise JDExtractionError(f"Mistral API network error: {exc}") from exc

    if response.status_code >= 400:
        logger.error("Mistral API error %s: %s", response.status_code, response.text)
        raise JDExtractionError(
            f"Mistral API returned status {response.status_code}.",
            status_code=502,
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise JDExtractionError("Unexpected Mistral API response format.") from exc

    try:
        parsed = json.loads(_strip_json_fence(content))
        return JobRequirements.model_validate(parsed)
    except json.JSONDecodeError as exc:
        raise JDExtractionError("Mistral returned malformed JSON.") from exc
    except Exception as exc:
        raise JDExtractionError(f"Failed to validate extracted requirements: {exc}") from exc
