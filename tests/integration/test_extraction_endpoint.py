"""
Integration tests for POST /documents/extract/invoice

These tests go through the full HTTP stack:
  HTTP request → FastAPI → document_router → loader → InvoiceExtractor → response

All test documents are created programmatically (no binary blobs in git).
"""
import io
from pathlib import Path

import fitz  # PyMuPDF
import pytest
from docx import Document
from fastapi.testclient import TestClient

from app.main import app

# ── Shared client (one lifespan for the whole test module) ────────────────────

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


# ── File factories ─────────────────────────────────────────────────────────────

def _make_invoice_pdf(tmp_path: Path, text: str) -> Path:
    """Create a single-page PDF containing the supplied text."""
    path = tmp_path / "invoice.pdf"
    doc: fitz.Document = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((50, 50), text, fontsize=11)  # type: ignore[attr-defined]
    doc.save(str(path))
    doc.close()
    return path


def _make_invoice_docx(tmp_path: Path, text: str) -> Path:
    """Create a DOCX file with each line as a paragraph."""
    path = tmp_path / "invoice.docx"
    doc = Document()
    for line in text.splitlines():
        doc.add_paragraph(line)
    doc.save(str(path))
    return path


# ── Shared invoice text ────────────────────────────────────────────────────────

INVOICE_TEXT = """\
Skyline Solutions Pvt. Ltd.

Invoice Number: INV-2024-555
Invoice Date: 10/03/2024
Due Date: 09/04/2024

Grand Total: USD 3,750.00
"""


# ══════════════════════════════════════════════════════════════════════════════
# Happy-path tests
# ══════════════════════════════════════════════════════════════════════════════

class TestExtractInvoiceEndpoint:

    def test_pdf_returns_200(self, client, tmp_path):
        pdf_path = _make_invoice_pdf(tmp_path, INVOICE_TEXT)
        with open(pdf_path, "rb") as f:
            response = client.post(
                "/documents/extract/invoice",
                files={"file": ("invoice.pdf", f, "application/pdf")},
            )
        assert response.status_code == 200

    def test_pdf_response_has_required_keys(self, client, tmp_path):
        pdf_path = _make_invoice_pdf(tmp_path, INVOICE_TEXT)
        with open(pdf_path, "rb") as f:
            data = client.post(
                "/documents/extract/invoice",
                files={"file": ("invoice.pdf", f, "application/pdf")},
            ).json()

        assert "document_type" in data
        assert "fields" in data
        assert "confidence" in data
        assert "overall_confidence" in data
        assert "extraction_warnings" in data
        assert "raw_text_length" in data

    def test_pdf_document_type_is_invoice(self, client, tmp_path):
        pdf_path = _make_invoice_pdf(tmp_path, INVOICE_TEXT)
        with open(pdf_path, "rb") as f:
            data = client.post(
                "/documents/extract/invoice",
                files={"file": ("invoice.pdf", f, "application/pdf")},
            ).json()
        assert data["document_type"] == "invoice"

    def test_pdf_invoice_number_extracted(self, client, tmp_path):
        pdf_path = _make_invoice_pdf(tmp_path, INVOICE_TEXT)
        with open(pdf_path, "rb") as f:
            data = client.post(
                "/documents/extract/invoice",
                files={"file": ("invoice.pdf", f, "application/pdf")},
            ).json()
        assert data["fields"]["invoice_number"] == "INV-2024-555"

    def test_pdf_total_amount_extracted(self, client, tmp_path):
        pdf_path = _make_invoice_pdf(tmp_path, INVOICE_TEXT)
        with open(pdf_path, "rb") as f:
            data = client.post(
                "/documents/extract/invoice",
                files={"file": ("invoice.pdf", f, "application/pdf")},
            ).json()
        assert data["fields"]["total_amount"] == 3750.0

    def test_pdf_currency_is_usd(self, client, tmp_path):
        pdf_path = _make_invoice_pdf(tmp_path, INVOICE_TEXT)
        with open(pdf_path, "rb") as f:
            data = client.post(
                "/documents/extract/invoice",
                files={"file": ("invoice.pdf", f, "application/pdf")},
            ).json()
        assert data["fields"]["currency"] == "USD"

    def test_pdf_confidence_scores_in_range(self, client, tmp_path):
        pdf_path = _make_invoice_pdf(tmp_path, INVOICE_TEXT)
        with open(pdf_path, "rb") as f:
            data = client.post(
                "/documents/extract/invoice",
                files={"file": ("invoice.pdf", f, "application/pdf")},
            ).json()
        for field, score in data["confidence"].items():
            assert 0.0 <= score <= 1.0, f"Confidence for {field} out of range: {score}"

    def test_docx_returns_200(self, client, tmp_path):
        docx_path = _make_invoice_docx(tmp_path, INVOICE_TEXT)
        with open(docx_path, "rb") as f:
            response = client.post(
                "/documents/extract/invoice",
                files={"file": ("invoice.docx", f,
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            )
        assert response.status_code == 200

    def test_docx_invoice_number_extracted(self, client, tmp_path):
        docx_path = _make_invoice_docx(tmp_path, INVOICE_TEXT)
        with open(docx_path, "rb") as f:
            data = client.post(
                "/documents/extract/invoice",
                files={"file": ("invoice.docx", f,
                                "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            ).json()
        assert data["fields"]["invoice_number"] == "INV-2024-555"

    def test_raw_text_length_positive(self, client, tmp_path):
        pdf_path = _make_invoice_pdf(tmp_path, INVOICE_TEXT)
        with open(pdf_path, "rb") as f:
            data = client.post(
                "/documents/extract/invoice",
                files={"file": ("invoice.pdf", f, "application/pdf")},
            ).json()
        assert data["raw_text_length"] > 0


# ══════════════════════════════════════════════════════════════════════════════
# Error-handling tests
# ══════════════════════════════════════════════════════════════════════════════

class TestExtractInvoiceErrors:

    def test_unsupported_file_type_returns_415(self, client, tmp_path):
        """An EXE file must be rejected with 415 Unsupported Media Type."""
        exe_path = tmp_path / "bad.exe"
        exe_path.write_bytes(b"MZ" + b"\x00" * 100)
        with open(exe_path, "rb") as f:
            response = client.post(
                "/documents/extract/invoice",
                files={"file": ("bad.exe", f, "application/octet-stream")},
            )
        assert response.status_code == 415

    def test_encrypted_pdf_without_password_returns_401(self, client, tmp_path):
        """Password-protected PDF without password → 401 Unauthorized."""
        path = tmp_path / "locked.pdf"
        password = "secret"
        doc: fitz.Document = fitz.open()
        page = doc.new_page()                # type: ignore[attr-defined]
        page.insert_text((50, 50), "Secret invoice", fontsize=12)  # type: ignore[attr-defined]
        aes256 = getattr(fitz, "PDF_ENCRYPT_AES_256", 6)
        doc.save(str(path), encryption=aes256, user_pw=password, owner_pw=password)
        doc.close()

        with open(path, "rb") as f:
            response = client.post(
                "/documents/extract/invoice",
                files={"file": ("locked.pdf", f, "application/pdf")},
            )
        assert response.status_code == 401

    def test_encrypted_pdf_with_correct_password_returns_200(self, client, tmp_path):
        """Password-protected PDF with correct password → 200 OK."""
        path = tmp_path / "locked2.pdf"
        password = "secret"
        doc: fitz.Document = fitz.open()
        page = doc.new_page()                # type: ignore[attr-defined]
        page.insert_text((50, 50), "Grand Total: 999.00", fontsize=12)  # type: ignore[attr-defined]
        aes256 = getattr(fitz, "PDF_ENCRYPT_AES_256", 6)
        doc.save(str(path), encryption=aes256, user_pw=password, owner_pw=password)
        doc.close()

        with open(path, "rb") as f:
            response = client.post(
                "/documents/extract/invoice",
                files={"file": ("locked2.pdf", f, "application/pdf")},
                data={"password": password},
            )
        assert response.status_code == 200

    def test_no_file_field_returns_422(self, client):
        """Missing 'file' field → 422 Unprocessable Entity (FastAPI validation)."""
        response = client.post("/documents/extract/invoice")
        assert response.status_code == 422

    def test_empty_invoice_returns_200_structured_fields(self, client, tmp_path):
        """A PDF with no invoice data returns 200 with None for specific fields."""
        path = _make_invoice_pdf(tmp_path, "Hello world, no invoice here.")
        with open(path, "rb") as f:
            data = client.post(
                "/documents/extract/invoice",
                files={"file": ("empty.pdf", f, "application/pdf")},
            ).json()
        # invoice_number and total_amount definitely cannot be found
        assert data["fields"]["invoice_number"] is None
        assert data["fields"]["total_amount"] is None
        # overall_confidence may be non-zero if vendor heuristic fires (acceptable)
        assert 0.0 <= data["overall_confidence"] <= 1.0
