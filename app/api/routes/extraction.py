"""
Extraction routes — convert uploaded documents into structured data.

Endpoint
────────
  POST /documents/extract/invoice
    Accepts the same file types as the upload endpoint (PDF, JPEG, PNG, DOCX).
    Runs the full pipeline: load → OCR → extract → return structured JSON.

Design notes
────────────
  • We reuse the exact same loaders from services/ (no duplication).
  • The extraction layer never touches files — it only sees plain text.
  • Passwords for encrypted PDFs are passed as an optional form field.
  • The response schema is InvoiceExtractionResult (fully typed Pydantic model).
"""
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.logging_config import get_logger
from app.extraction.invoice_extractor import InvoiceExtractor
from app.extraction.schemas import InvoiceExtractionResult
from app.services.document_router import UnsupportedFileTypeError, get_loader
from app.services.pdf_loader import PasswordProtectedError

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["extraction"])


# ── Invoice extraction endpoint ────────────────────────────────────────────────

@router.post(
    "/extract/invoice",
    response_model=InvoiceExtractionResult,
    summary="Extract structured invoice fields from a document",
    response_description="Structured invoice fields with per-field confidence scores",
)
async def extract_invoice(
    file: UploadFile = File(..., description="PDF, JPEG, PNG, TIFF, WEBP, or DOCX"),
    password: str    = Form("", description="Password for encrypted PDFs (leave blank if not encrypted)"),
) -> InvoiceExtractionResult:
    """
    Upload a document and extract structured invoice fields.

    **Extraction pipeline:**
    1. Save file to a temporary path (UUID name, auto-deleted after processing)
    2. Detect file type and select the right loader (PDF / Image / DOCX)
    3. Extract raw text (with OCR if needed)
    4. Run InvoiceExtractor on the raw text
    5. Return InvoiceExtractionResult with fields + confidence scores

    **Response fields:**
    - `fields` — the extracted values (vendor_name, invoice_number, dates, amounts, ...)
    - `confidence` — per-field score from 0.0 (not found) to 1.0 (certain)
    - `overall_confidence` — mean of all non-zero field scores
    - `extraction_warnings` — list of non-fatal issues encountered
    - `raw_text_length` — character count of the text passed to the extractor
    """
    t_start = time.perf_counter()

    # ── Validate file presence ────────────────────────────────────────────────
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided.",
        )

    # ── Save to a temporary upload path ──────────────────────────────────────
    # We keep the original extension so loaders can disambiguate DOCX vs ZIP.
    original_ext = Path(file.filename).suffix.lower()
    tmp_name     = f"{uuid.uuid4().hex}{original_ext}"
    tmp_path     = settings.upload_path / tmp_name

    settings.upload_path.mkdir(parents=True, exist_ok=True)

    try:
        content = await file.read()

        # Enforce file size limit
        max_bytes = settings.max_file_size_bytes
        if len(content) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of {settings.max_file_size_mb} MB.",
            )

        tmp_path.write_bytes(content)

        logger.info(
            "Extraction request received",
            extra={
                "doc": file.filename,
                "size_bytes": len(content),
                "tmp": tmp_name,
            },
        )

        # ── Select loader & extract text ──────────────────────────────────────
        try:
            loader = get_loader(tmp_path, password=password or None)
        except (ValueError, UnsupportedFileTypeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=str(exc),
            ) from exc

        try:
            raw_text = loader.extract_text()
        except PasswordProtectedError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This PDF is password-protected. Provide the password via the 'password' form field.",
            )
        except Exception as exc:
            logger.error("Text extraction failed", extra={"doc": file.filename, "error": repr(exc)})
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to extract text from document: {exc}",
            ) from exc

        # ── Run invoice extractor ─────────────────────────────────────────────
        extractor = InvoiceExtractor(raw_text)
        result    = extractor.extract()

        duration_ms = round((time.perf_counter() - t_start) * 1000, 1)
        logger.info(
            "Extraction completed",
            extra={
                "doc": file.filename,
                "overall_confidence": result.overall_confidence,
                "duration_ms": duration_ms,
            },
        )

        return result

    finally:
        # Always clean up the temp file — even on exceptions
        tmp_path.unlink(missing_ok=True)
