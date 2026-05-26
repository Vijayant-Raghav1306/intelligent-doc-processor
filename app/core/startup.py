"""
Startup validation — checks that the runtime environment is healthy before
the server starts accepting requests.

Design philosophy
─────────────────
  WARN, don't crash (unless truly fatal).

  This application is designed to degrade gracefully:
    • No Tesseract → image OCR returns empty text, extraction returns no fields.
    • No spaCy model → regex-only extraction (still useful).
    • No writable dirs → we create them on the fly; error only if creation fails.

  We log every check result at startup so operators know the exact capability
  level of the running instance without reading source code.

Called from app/main.py lifespan, before the server starts serving.
"""
import shutil
import subprocess
from pathlib import Path

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def run_startup_checks() -> dict[str, bool]:
    """
    Run all pre-flight checks and return a status dict.

    Returns:
        {
            "tesseract": bool,   True if the OCR binary is reachable
            "upload_dir": bool,  True if the upload directory is writable
            "output_dir": bool,  True if the output directory is writable
        }

    Does NOT check spaCy — that's handled by nlp_service.load_nlp() which
    runs right after this and has its own logging.
    """
    status: dict[str, bool] = {}

    status["tesseract"]  = _check_tesseract()
    status["upload_dir"] = _check_directory(settings.upload_path, "upload")
    status["output_dir"] = _check_directory(settings.output_path, "output")

    # Log a clean summary line
    all_ok = all(status.values())
    logger.info(
        "startup_checks_complete",
        extra={
            "all_ok":      all_ok,
            "tesseract":   status["tesseract"],
            "upload_dir":  status["upload_dir"],
            "output_dir":  status["output_dir"],
        },
    )

    return status


# ── Individual checks ──────────────────────────────────────────────────────────

def _check_tesseract() -> bool:
    """
    Verify that the Tesseract OCR binary is reachable.

    Strategy:
      1. If settings.tesseract_cmd is a full path → check that Path exists.
      2. Otherwise assume it's a name on PATH → use shutil.which().
      3. As a final confirmation, run `tesseract --version` and check exit code.

    A missing Tesseract is a WARNING, not a fatal error — PDFs and DOCX files
    don't need OCR.  Only scanned images will silently return empty text.
    """
    cmd = settings.tesseract_cmd

    # Path-based check (full path given in settings)
    if cmd not in ("tesseract",) and not Path(cmd).exists():
        logger.warning(
            "Tesseract binary not found at configured path — "
            "image OCR will fail. "
            f"Fix: install Tesseract or update TESSERACT_CMD in .env. "
            f"Configured path: {cmd}",
        )
        return False

    # PATH-based check (just the binary name)
    if shutil.which(cmd) is None and not Path(cmd).exists():
        logger.warning(
            "Tesseract not found on PATH — image OCR will fail. "
            "Fix: `apt-get install tesseract-ocr` (Linux) or "
            "`brew install tesseract` (macOS) or "
            "download from https://github.com/UB-Mannheim/tesseract/wiki (Windows).",
        )
        return False

    # Run `tesseract --version` to confirm binary is executable
    try:
        result = subprocess.run(
            [cmd, "--version"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            # e.g. "tesseract 5.3.4\n ..."
            version_line = (result.stdout or result.stderr).decode(errors="replace").splitlines()[0]
            logger.info("Tesseract ready", extra={"version": version_line})
            return True
        else:
            logger.warning("Tesseract binary found but returned non-zero exit code.")
            return False
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        logger.warning(f"Tesseract check failed: {exc}")
        return False


def _check_directory(path: Path, name: str) -> bool:
    """
    Ensure a directory exists and is writable.

    Creates the directory if it doesn't exist.
    Logs an error (but does not raise) if creation fails.
    """
    try:
        path.mkdir(parents=True, exist_ok=True)
        # Quick write test: create and delete a probe file
        probe = path / ".write_probe"
        probe.write_text("ok")
        probe.unlink()
        logger.info(f"{name} directory ready", extra={"path": str(path)})
        return True
    except OSError as exc:
        logger.error(
            f"{name} directory is not writable — file operations will fail.",
            extra={"path": str(path), "error": str(exc)},
        )
        return False
