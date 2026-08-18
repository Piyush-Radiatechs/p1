"""FastAPI backend for AI-powered JD → LinkedIn candidate search.

COMPLIANCE BOUNDARY:
This API generates Google X-Ray queries and inspects SerpApi search results.
It does NOT log into LinkedIn, scrape profiles, or use browser automation.
Recruiters manually open discovered LinkedIn URLs.
"""

import logging
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.exceptions import AppError
from app.services.document_parser import SUPPORTED_EXTENSIONS
from app.services.pipeline import process_jd_file, process_jd_text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Candidate Search API",
    description="Upload a JD (PDF, Word, or text) or submit JD text to extract requirements, generate X-Ray queries, and discover LinkedIn profiles via Google search.",
    version="0.1.0",
)


@app.get("/health")
async def health():
    settings = get_settings()
    return {
        "status": "ok",
        "mistral_configured": settings.mistral_configured,
        "serpapi_configured": settings.serpapi_configured,
    }


@app.post("/search-candidates")
async def search_candidates(
    file: UploadFile | None = File(None),
    jd_text: str | None = Form(None),
):
    has_file = file is not None and bool(file.filename)
    has_text = bool(jd_text and jd_text.strip())
    if has_file == has_text:
        return JSONResponse(
            status_code=400,
            content={"detail": "Provide a JD file or jd_text (exactly one)."},
        )

    try:
        if has_file:
            assert file is not None and file.filename
            suffix = Path(file.filename).suffix.lower()
            if suffix not in SUPPORTED_EXTENSIONS:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Please upload a PDF, Word (.docx), or text (.txt) file."},
                )
            file_bytes = await file.read()
            if not file_bytes:
                return JSONResponse(
                    status_code=400,
                    content={"detail": "Uploaded file is empty."},
                )
            result = await process_jd_file(file_bytes, filename=file.filename)
        else:
            result = await process_jd_text(jd_text, filename="pasted_jd.txt")
        return result
    except AppError as exc:
        logger.error("Pipeline error: %s", exc.message)
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )
    except Exception as exc:
        logger.exception("Unexpected error in search-candidates")
        return JSONResponse(
            status_code=500,
            content={"detail": "An unexpected error occurred. Please try again."},
        )
