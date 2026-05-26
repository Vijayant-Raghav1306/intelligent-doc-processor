from pathlib import Path

import filetype

from app.core.config import settings
from app.core.logging_config import get_logger
from app.services.base_loader import BaseLoader
from app.services.docx_loader import DocxLoader
from app.services.image_loader import ImageLoader
from app.services.pdf_loader import PasswordProtectedError, PdfLoader  # noqa: F401

logger = get_logger(__name__)

# DOCX MIME type â€” long string, defined once here
_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Maps detected MIME type â†’ loader class
# To add a new format: add one entry here, write the loader, done.
_MIME_TO_LOADER: dict[str, type[BaseLoader]] = {
    "application/pdf": PdfLoader,
    "image/jpeg":      ImageLoader,
    "image/png":       ImageLoader,
    "image/tiff":      ImageLoader,
    "image/webp":      ImageLoader,
    _DOCX_MIME:        DocxLoader,
}


class UnsupportedFileTypeError(Exception):
    """Raised when the uploaded file's type has no registered loader."""


def _detect_mime_type(file_path: Path) -> str:
    """
    Detect the real file type by reading magic bytes â€” not the file extension.
    Special case: DOCX is a ZIP internally, so filetype returns 'application/zip'.
    We disambiguate using the extension only for this one known ambiguous case.
    """
    kind = filetype.guess(str(file_path))

    if kind is None:
        # filetype couldn't match any known signature
        # Last resort: trust .docx extension since DOCX ZIPs can evade byte detection
        if file_path.suffix.lower() == ".docx":
            return _DOCX_MIME
        raise UnsupportedFileTypeError(
            f"Cannot detect file type for '{file_path.name}'. "
            "Ensure the file is not corrupted."
        )

    # DOCX is technically a ZIP â€” filetype sees PK magic bytes and returns application/zip
    # Disambiguate using extension as the secondary signal
    if kind.mime == "application/zip" and file_path.suffix.lower() == ".docx":
        return _DOCX_MIME

    return kind.mime


def get_loader(file_path: str | Path, password: str | None = None) -> BaseLoader:
    """
    Detect the file type and return the correct loader instance.

    Args:
        file_path: Path to the file on disk.
        password:  Optional password for encrypted PDFs.

    Returns:
        A BaseLoader subclass ready to call .extract_text() / .get_preview_image() on.

    Raises:
        UnsupportedFileTypeError: File type is not supported or cannot be detected.
        PasswordProtectedError:   PDF is encrypted and password is missing/wrong.
        FileNotFoundError:        File does not exist (raised by BaseLoader.__init__).
    """
    path = Path(file_path)
    mime_type = _detect_mime_type(path)
    logger.info("mime_detected", extra={"doc": path.name, "mime": mime_type})

    if mime_type not in settings.allowed_mime_types:
        logger.warning(
            "unsupported_mime",
            extra={"doc": path.name, "mime": mime_type},
        )
        raise UnsupportedFileTypeError(
            f"File type '{mime_type}' is not supported. "
            f"Allowed types: {', '.join(settings.allowed_mime_types)}"
        )

    loader_class = _MIME_TO_LOADER.get(mime_type)
    if loader_class is None:
        raise UnsupportedFileTypeError(f"No loader registered for '{mime_type}'.")

    logger.info(
        "loader_selected",
        extra={"doc": path.name, "loader": loader_class.__name__},
    )

    # PdfLoader is the only loader that accepts an optional password argument
    if loader_class is PdfLoader:
        return PdfLoader(file_path, password=password)

    return loader_class(file_path)
