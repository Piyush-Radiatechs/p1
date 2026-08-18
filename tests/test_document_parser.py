"""Unit tests for document text extraction (PDF, Word, plain text)."""

from io import BytesIO

import fitz
import pytest
from docx import Document

from app.exceptions import DocumentExtractionError, PDFExtractionError
from app.services.document_parser import (
    extract_document_text,
    extract_docx_text,
    extract_plain_text,
)


def _make_docx_with_text(text: str) -> bytes:
    document = Document()
    document.add_paragraph(text)
    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _make_pdf_with_text(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_extract_docx_text_valid():
    docx_bytes = _make_docx_with_text("Windchill Developer with Java experience.")
    result = extract_docx_text(docx_bytes)
    assert "Windchill Developer" in result


def test_extract_docx_text_empty_bytes():
    with pytest.raises(DocumentExtractionError, match="empty"):
        extract_docx_text(b"")


def test_extract_plain_text_valid():
    result = extract_plain_text("Senior Python engineer. Remote. 5+ years.".encode("utf-8"))
    assert "Senior Python engineer" in result


def test_extract_plain_text_empty():
    with pytest.raises(DocumentExtractionError, match="empty"):
        extract_plain_text(b"   \n  ")


def test_extract_document_text_dispatches_by_extension():
    pdf_bytes = _make_pdf_with_text("PDF job description.")
    assert "PDF job description" in extract_document_text(pdf_bytes, "jd.pdf")

    docx_bytes = _make_docx_with_text("Word job description.")
    assert "Word job description" in extract_document_text(docx_bytes, "jd.docx")

    txt_bytes = b"Text job description."
    assert "Text job description" in extract_document_text(txt_bytes, "jd.txt")


def test_extract_document_text_unsupported_type():
    with pytest.raises(DocumentExtractionError, match="Unsupported file type"):
        extract_document_text(b"not-a-jd", "resume.xlsx")


def test_extract_document_text_invalid_pdf_still_raises_pdf_error():
    with pytest.raises(PDFExtractionError):
        extract_document_text(b"%PDF-not-valid", "broken.pdf")
