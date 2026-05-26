import time
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.document_router import (
    PasswordProtectedError,
    UnsupportedFileTypeError,
    get_loader,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


# â”€â”€ Response schema â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class DocumentResponse(BaseModel):
    filename: str          # original uploaded filename
    file_type: str         # detected MIME type
    page_count: int        # number of pages (always 1 for images/docx)
    char_count: int        # length of extracted text
    text: str              # full extracted text
    preview_url: str       # relative URL to the saved preview image
    metadata: dict         # loader-specific metadata (author, dimensions, etc.)


# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _unique_stem() -> str:
    """Generate a UUID-based filename stem â€” never use the client's filename directly."""
    return uuid.uuid4().hex


async def _save_upload(file: UploadFile, dest: Path) -> None:
    """Read UploadFile bytes and write to disk asynchronously."""
    contents = await file.read()
    async with aiofiles.open(dest, "wb") as f:
        await f.write(contents)


# â”€â”€ Endpoint â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@router.post("/upload", response_model=DocumentResponse, status_code=200)
async def upload_document(
    file: UploadFile = File(..., description="PDF, image (JPEG/PNG/TIFF/WEBP), or DOCX file"),
    password: str | None = Form(None, description="Password for encrypted PDFs"),
):
    """
    Upload a document and receive extracted text + a cleaned preview image.

    Supports: PDF (including scanned + password-protected), JPEG, PNG, TIFF, WEBP, DOCX.
    """

    start = time.perf_counter()
    size_kb = round((file.size or 0) / 1024, 1)
    logger.info(
        "upload_start",
        extra={"doc": file.filename, "size_kb": size_kb},
    )

    # â”€â”€ 1. File size guard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if file.size and file.size > settings.max_file_size_bytes:
        logger.warning(
            "upload_rejected_size",
            extra={"doc": file.filename, "size_kb": size_kb, "limit_mb": settings.max_file_size_mb},
        )
        raise HTTPException(
            status_code=413,
            detail=(
                f"File '{file.filename}' is {file.size / 1_048_576:.1f} MB. "
                f"Maximum allowed size is {settings.max_file_size_mb} MB."
            ),
        )

    # â”€â”€ 2. Save uploaded file to disk with a safe, unique name â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    original_suffix = Path(file.filename or "upload").suffix.lower()
    safe_stem = _unique_stem()
    upload_path = settings.upload_path / f"{safe_stem}{original_suffix}"

    try:
        await _save_upload(file, upload_path)
    except OSError as e:
        logger.error("upload_save_failed", extra={"doc": file.filename, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {e}")

    # â”€â”€ 3. Route to the correct loader â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        loader = get_loader(upload_path, password=password)

    except UnsupportedFileTypeError as e:
        upload_path.unlink(missing_ok=True)
        logger.warning("upload_rejected_type", extra={"doc": file.filename, "error": str(e)})
        raise HTTPException(status_code=415, detail=str(e))

    except PasswordProtectedError as e:
        upload_path.unlink(missing_ok=True)
        logger.warning("upload_rejected_password", extra={"doc": file.filename})
        raise HTTPException(status_code=401, detail=str(e))

    # â”€â”€ 4. Extract text, preview, metadata â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    try:
        text = loader.extract_text()
        preview_image = loader.get_preview_image()
        metadata = loader.get_metadata()

    except PasswordProtectedError as e:
        upload_path.unlink(missing_ok=True)
        logger.warning("upload_rejected_password", extra={"doc": file.filename})
        raise HTTPException(status_code=401, detail=str(e))

    except Exception as e:
        upload_path.unlink(missing_ok=True)
        logger.error(
            "processing_failed",
            extra={"doc": file.filename, "error": type(e).__name__, "detail": str(e)},
        )
        raise HTTPException(status_code=500, detail=f"Processing failed: {e}")

    # â”€â”€ 5. Save preview image â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    preview_filename = f"{safe_stem}_preview.jpg"
    preview_path = settings.output_path / preview_filename

    try:
        preview_image.convert("RGB").save(preview_path, format="JPEG", quality=85)
    except OSError as e:
        logger.error("preview_save_failed", extra={"doc": file.filename, "error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to save preview image: {e}")

    # â”€â”€ 6. Return structured response â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    duration_ms = round((time.perf_counter() - start) * 1000, 1)
    logger.info(
        "upload_complete",
        extra={
            "doc": file.filename,
            "pages": metadata.get("page_count", 1),
            "chars": len(text),
            "duration_ms": duration_ms,
        },
    )

    return DocumentResponse(
        filename=file.filename or "unknown",
        file_type=metadata.get("file_type", original_suffix.lstrip(".")),
        page_count=metadata.get("page_count", 1),
        char_count=len(text),
        text=text,
        preview_url=f"/outputs/{preview_filename}",
        metadata=metadata,
    )


