"""FastAPI backend for AI-powered JD → LinkedIn candidate search.

COMPLIANCE BOUNDARY:
This API generates Google X-Ray queries and inspects SerpApi search results.
It does NOT log into LinkedIn, scrape profiles, or use browser automation.
Recruiters manually open discovered LinkedIn URLs.
"""

import logging

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.exceptions import AppError
from app.services.pipeline import process_jd_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Candidate Search API",
    description="Upload a JD PDF to extract requirements, generate X-Ray queries, and discover LinkedIn profiles via Google search.",
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
async def search_candidates(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        return JSONResponse(
            status_code=400,
            content={"detail": "Please upload a PDF file."},
        )

    pdf_bytes = await file.read()
    if not pdf_bytes:
        return JSONResponse(
            status_code=400,
            content={"detail": "Uploaded file is empty."},
        )

    try:
        result = await process_jd_pdf(pdf_bytes, filename=file.filename)
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
