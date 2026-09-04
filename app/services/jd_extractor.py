"""Mistral-powered JD requirement extraction.

COMPLIANCE: This service only parses job-description text. It does not access
LinkedIn or any candidate profile data.
"""

import json
import logging
import os
import re

import httpx

from app.config import Settings, get_settings
from app.exceptions import JDExtractionError
from app.models.jd import JobRequirements
from app.utils.text_utils import merge_jd_locations

logger = logging.getLogger(__name__)

GROQ_CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
MISTRAL_CHAT_URL = "https://api.mistral.ai/v1/chat/completions"

SYSTEM_PROMPT = """You are an expert technical recruitment sourcer. Extract structured job requirements from a job description to build high-converting Google X-Ray search queries for LinkedIn profiles.

Extraction Rules:
1. Job Titles:
   - Extract the primary role title and 2-4 realistic, widely-used LinkedIn headline titles for this role.
   - Example: For "PTC Windchill Specialist", extract ["Windchill Developer", "Windchill Consultant", "PTC Windchill Specialist", "PLM Developer"].
   - Titles must be clean professional titles. Do NOT include location, department, or company names in the title.

2. Technical Skills:
   - Extract ONLY canonical, standalone technology keywords (e.g., "Windchill", "Java", "Python", "AWS", "PDMLink", "Docker", "Kubernetes", "OIR").
   - NEVER include verb phrases or compound descriptions (e.g., use "Windchill", NOT "PTC Windchill development"; use "REST", NOT "REST/SOAP Web Services"; use "OIR", NOT "Object Initialization Rules (OIR)").
   - Never include generic buzzwords or soft skills like "Agile", "Communication", "Problem Solving", "Team Player", "Fast Learner".
   - Put the 2-3 most critical, non-negotiable core technologies FIRST.

3. Preferred Skills:
   - Secondary tools, secondary frameworks, or nice-to-have technologies as clean standalone keywords.

4. Locations:
   - Extract ALL work locations (city, state, AND country) that the candidate must be in or willing to cover.
   - Put the primary/base work location first. "US Based", "USA", "United States", Green Card, or US citizen means United States is the primary location.
   - Travel destinations are extra locations — never replace the primary country with only travel countries.

5. Experience:
   - Extract experience range in years when mentioned (min_years and max_years as integers, or null).

6. Exclusions:
   - When the JD targets experienced hires (e.g. 3+ or 5+ years), include: ["intern", "fresher"].

Return machine-readable JSON only — no markdown fence, no commentary.

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
    """Convert raw JD text into a validated JobRequirements model via Groq or Mistral."""
    settings = settings or get_settings()

    groq_api_key = getattr(settings, "groq_api_key", "").strip() or os.environ.get("GROQ_API_KEY", "").strip()
    groq_model = getattr(settings, "groq_model", "openai/gpt-oss-120b") or os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")
    mistral_api_key = getattr(settings, "mistral_api_key", "").strip() or os.environ.get("MISTRAL_API_KEY", "").strip()
    mistral_model = getattr(settings, "mistral_model", "mistral-small-latest") or os.environ.get("MISTRAL_MODEL", "mistral-small-latest")

    groq_configured = getattr(settings, "groq_configured", bool(groq_api_key))
    mistral_configured = getattr(settings, "mistral_configured", bool(mistral_api_key))

    if groq_configured or groq_api_key:
        provider = "Groq"
        api_url = GROQ_CHAT_URL
        api_key = groq_api_key
        model = groq_model
    elif mistral_configured or mistral_api_key:
        provider = "Mistral"
        api_url = MISTRAL_CHAT_URL
        api_key = mistral_api_key
        model = mistral_model
    else:
        raise JDExtractionError("Neither GROQ_API_KEY nor MISTRAL_API_KEY is configured.")

    if not jd_text.strip():
        raise JDExtractionError("Job description text is empty.")

    payload = {
        "model": model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": jd_text[:120_000]},
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(api_url, json=payload, headers=headers)
    except httpx.TimeoutException as exc:
        raise JDExtractionError(f"{provider} API request timed out.") from exc
    except httpx.RequestError as exc:
        raise JDExtractionError(f"{provider} API network error: {exc}") from exc

    if response.status_code >= 400:
        logger.error("%s API error %s: %s", provider, response.status_code, response.text)
        raise JDExtractionError(
            f"{provider} API returned status {response.status_code}.",
            status_code=502,
        )

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise JDExtractionError(f"Unexpected {provider} API response format.") from exc

    try:
        parsed = json.loads(_strip_json_fence(content))
        requirements = JobRequirements.model_validate(parsed)
        requirements.locations = merge_jd_locations(requirements.locations, jd_text)
        min_years = requirements.experience.min_years if requirements.experience else None
        if min_years is not None and min_years >= 3:
            extra = ["intern", "internship", "fresher", "entry-level", "trainee"]
            requirements.exclusions = list(dict.fromkeys(list(requirements.exclusions or []) + extra))
        return requirements
    except json.JSONDecodeError as exc:
        raise JDExtractionError(f"{provider} returned malformed JSON.") from exc
    except Exception as exc:
        raise JDExtractionError(f"Failed to validate extracted requirements: {exc}") from exc
