import fitz  # PyMuPDF
import pdfplumber
import pytesseract
from PIL import Image

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.base_loader import BaseLoader

logger = get_logger(__name__)


class PasswordProtectedError(Exception):
    """Raised when a PDF is encrypted and no valid password was supplied."""


class PdfLoader(BaseLoader):

    def __init__(self, file_path, password: str | None = None):
        self.password = password
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
        super().__init__(file_path)  # validates file exists via BaseLoader

    # â”€â”€ Internal helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _open_fitz_doc(self) -> fitz.Document:
        """
        Open the PDF with PyMuPDF and handle encryption.
        Raises PasswordProtectedError early so callers get a clean error,
        not a cryptic fitz exception buried in a stack trace.
        """
        doc = fitz.open(str(self.file_path))

        if doc.is_encrypted:
            authenticated = self.password and doc.authenticate(self.password)
            if not authenticated:
                doc.close()
                logger.warning(
                    "password_auth_failed",
                    extra={"doc": self.file_path.name, "password_provided": bool(self.password)},
                )
                raise PasswordProtectedError(
                    f"'{self.file_path.name}' is password-protected. "
                    "Provide the correct password to proceed."
                )
            logger.info("password_auth_success", extra={"doc": self.file_path.name})

        return doc

    def _render_page_as_image(self, fitz_doc: fitz.Document, page_index: int) -> Image.Image:
        """
        Render a single PDF page to a PIL Image using PyMuPDF.
        Matrix(2, 2) = 2Ã— zoom â†’ 144 DPI, sharp enough for reliable OCR.
        Default 72 DPI is too blurry for Tesseract.
        """
        page = fitz_doc.load_page(page_index)
        mat = fitz.Matrix(2.0, 2.0)
        # Compatibility: some PyMuPDF versions expose get_pixmap, older ones use getPixmap
        get_pixmap = getattr(page, "get_pixmap", None) or getattr(page, "getPixmap", None)
        if get_pixmap is None:
            raise RuntimeError("PyMuPDF Page object has no get_pixmap/getPixmap method")
        pix = get_pixmap(matrix=mat, alpha=False)  # alpha=False â†’ RGB, no transparency
        return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

    def _ocr_page_image(self, page_image: Image.Image) -> str:
        """
        Run Tesseract OCR on an already-rendered PIL Image.
        Reuses the same pytesseract call as ImageLoader â€” no duplication of logic
        since we're working on an in-memory image already, not a file.
        """
        return pytesseract.image_to_string(page_image, lang="eng").strip()

    # â”€â”€ BaseLoader contract â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def extract_text(self) -> str:
        """
        Extract text from all pages.
        Strategy per page:
          1. Try pdfplumber (fast, accurate for native-text PDFs)
          2. If pdfplumber returns empty â†’ page is scanned â†’ render + OCR
        """
        fitz_doc = self._open_fitz_doc()
        all_pages_text = []
        total_pages = fitz_doc.page_count
        logger.info("pdf_opened", extra={"doc": self.file_path.name, "page_count": total_pages})

        try:
            with pdfplumber.open(str(self.file_path), password=self.password or "") as plumber_doc:
                for page_index, page in enumerate(plumber_doc.pages):
                    native_text = page.extract_text() or ""
                    page_num = page_index + 1

                    if native_text.strip():
                        all_pages_text.append(native_text.strip())
                        logger.info(
                            "page_extracted",
                            extra={
                                "doc": self.file_path.name,
                                "page": f"{page_num}/{total_pages}",
                                "method": "native",
                                "chars": len(native_text.strip()),
                            },
                        )
                    else:
                        # Page is image-only (scanned) â€” render it and OCR
                        logger.warning(
                            "ocr_fallback",
                            extra={
                                "doc": self.file_path.name,
                                "page": f"{page_num}/{total_pages}",
                                "reason": "empty_native_text",
                            },
                        )
                        page_image = self._render_page_as_image(fitz_doc, page_index)
                        ocr_text = self._ocr_page_image(page_image)
                        all_pages_text.append(ocr_text)
                        logger.info(
                            "page_extracted",
                            extra={
                                "doc": self.file_path.name,
                                "page": f"{page_num}/{total_pages}",
                                "method": "ocr",
                                "chars": len(ocr_text),
                            },
                        )
        finally:
            fitz_doc.close()  # always close fitz doc â€” it holds a file handle

        return "\n\n--- Page Break ---\n\n".join(all_pages_text)

    def get_preview_image(self) -> Image.Image:
        """Render the first page at 144 DPI as a PIL Image."""
        fitz_doc = self._open_fitz_doc()
        try:
            return self._render_page_as_image(fitz_doc, page_index=0)
        finally:
            fitz_doc.close()

    def get_metadata(self) -> dict:
        """
        Return page count, encryption status, and embedded PDF metadata.
        pdfplumber exposes the metadata dict from the PDF spec (Author, Title, etc.)
        """
        fitz_doc = self._open_fitz_doc()
        try:
            page_count = fitz_doc.page_count
            # fitz_doc.metadata can be None in some PDFs â€” fall back to empty dict
            fitz_meta = fitz_doc.metadata or {}
        finally:
            fitz_doc.close()

        return {
            "page_count": page_count,
            "file_type": "pdf",
            "file_size_bytes": self.get_file_size_bytes(),
            "is_encrypted": bool(self.password),
            "title": fitz_meta.get("title", ""),
            "author": fitz_meta.get("author", ""),
            "creator": fitz_meta.get("creator", ""),
        }

