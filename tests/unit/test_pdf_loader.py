"""
Unit tests for PdfLoader.
Covers: text extraction, password protection, metadata, preview rendering.
"""
import pytest
from PIL import Image

from app.services.pdf_loader import PasswordProtectedError, PdfLoader


class TestPdfLoaderContract:
    """Verify the BaseLoader contract is fulfilled correctly."""

    def test_extract_text_returns_string(self, tmp_pdf):
        text = PdfLoader(tmp_pdf).extract_text()
        assert isinstance(text, str)

    def test_get_preview_image_returns_pil_image(self, tmp_pdf):
        img = PdfLoader(tmp_pdf).get_preview_image()
        assert isinstance(img, Image.Image)

    def test_get_metadata_returns_dict(self, tmp_pdf):
        assert isinstance(PdfLoader(tmp_pdf).get_metadata(), dict)

    def test_missing_file_raises_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            PdfLoader("no_such_file.pdf")


class TestPdfTextExtraction:
    """Verify native text extraction works correctly."""

    def test_native_text_extracted(self, tmp_pdf):
        # conftest embeds "Hello from pytest PDF" as native text
        text = PdfLoader(tmp_pdf).extract_text()
        assert "Hello from pytest PDF" in text

    def test_text_is_non_empty(self, tmp_pdf):
        assert len(PdfLoader(tmp_pdf).extract_text()) > 0

    def test_multipage_separator_present(self, tmp_path):
        import fitz
        path = tmp_path / "multi.pdf"
        doc = fitz.open()
        for i in range(3):
            page = doc.new_page()
            page.insert_text((72, 72), f"Page {i + 1} content", fontsize=14)
        doc.save(str(path))
        doc.close()

        text = PdfLoader(path).extract_text()
        # Multi-page PDFs join pages with this separator
        assert "--- Page Break ---" in text


class TestPdfPasswordProtection:
    """Verify encrypted PDF handling."""

    def test_no_password_raises(self, tmp_pdf_encrypted):
        path, _ = tmp_pdf_encrypted
        with pytest.raises(PasswordProtectedError):
            PdfLoader(path).extract_text()

    def test_wrong_password_raises(self, tmp_pdf_encrypted):
        path, _ = tmp_pdf_encrypted
        with pytest.raises(PasswordProtectedError):
            PdfLoader(path, password="wrongpassword").extract_text()

    def test_correct_password_succeeds(self, tmp_pdf_encrypted):
        path, password = tmp_pdf_encrypted
        text = PdfLoader(path, password=password).extract_text()
        assert isinstance(text, str)

    def test_correct_password_preview_succeeds(self, tmp_pdf_encrypted):
        path, password = tmp_pdf_encrypted
        img = PdfLoader(path, password=password).get_preview_image()
        assert isinstance(img, Image.Image)


class TestPdfMetadata:
    """Verify metadata keys and values."""

    def test_required_keys_present(self, tmp_pdf):
        meta = PdfLoader(tmp_pdf).get_metadata()
        for key in ("page_count", "file_type", "file_size_bytes", "is_encrypted"):
            assert key in meta, f"Missing key: {key}"

    def test_page_count_single_page(self, tmp_pdf):
        assert PdfLoader(tmp_pdf).get_metadata()["page_count"] == 1

    def test_file_type_is_pdf(self, tmp_pdf):
        assert PdfLoader(tmp_pdf).get_metadata()["file_type"] == "pdf"

    def test_not_flagged_as_encrypted(self, tmp_pdf):
        # No password provided → is_encrypted should be False
        assert PdfLoader(tmp_pdf).get_metadata()["is_encrypted"] is False

    def test_file_size_bytes_positive(self, tmp_pdf):
        assert PdfLoader(tmp_pdf).get_metadata()["file_size_bytes"] > 0


class TestPdfPreview:
    """Verify preview image properties."""

    def test_preview_is_rgb(self, tmp_pdf):
        img = PdfLoader(tmp_pdf).get_preview_image()
        assert img.mode == "RGB"

    def test_preview_has_nonzero_dimensions(self, tmp_pdf):
        img = PdfLoader(tmp_pdf).get_preview_image()
        width, height = img.size
        assert width > 0 and height > 0