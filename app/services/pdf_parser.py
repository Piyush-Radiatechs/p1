"""PDF text extraction using PyMuPDF.

OCR is intentionally not implemented in V1. The structure allows adding an OCR
fallback layer later without changing callers.
"""

import fitz

from app.exceptions import PDFExtractionError


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from a multi-page PDF, preserving page order."""
    if not pdf_bytes:
        raise PDFExtractionError("Uploaded file is empty.")

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        raise PDFExtractionError(f"Invalid or corrupted PDF file: {exc}") from exc

    try:
        if document.page_count == 0:
            raise PDFExtractionError("PDF contains no pages.")

        pages: list[str] = []
        for page in document:
            page_text = page.get_text("text")
            if page_text:
                pages.append(page_text.strip())

        if not pages:
            raise PDFExtractionError(
                "No extractable text found in PDF. OCR is not supported in V1."
            )

        return "\n\n".join(pages)
    finally:
        document.close()
