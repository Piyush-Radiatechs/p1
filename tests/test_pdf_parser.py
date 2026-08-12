"""Unit tests for PDF text extraction."""

import fitz
import pytest

from app.exceptions import PDFExtractionError
from app.services.pdf_parser import extract_pdf_text


def _make_pdf_with_text(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_extract_pdf_text_valid():
    pdf_bytes = _make_pdf_with_text("Windchill Developer with Java experience.")
    result = extract_pdf_text(pdf_bytes)
    assert "Windchill Developer" in result


def test_extract_pdf_text_empty_pdf():
    doc = fitz.open()
    doc.new_page()  # blank page, no text
    pdf_bytes = doc.tobytes()
    doc.close()

    with pytest.raises(PDFExtractionError, match="No extractable text"):
        extract_pdf_text(pdf_bytes)


def test_extract_pdf_text_empty_bytes():
    with pytest.raises(PDFExtractionError, match="empty"):
        extract_pdf_text(b"")
