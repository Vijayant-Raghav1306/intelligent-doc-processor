from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes.document import router as document_router
from app.api.routes.extraction import router as extraction_router
from app.core.config import settings
from app.core.logging_config import get_logger, setup_logging
from app.core.startup import run_startup_checks
from app.extraction.nlp_service import is_nlp_available, load_nlp

logger = get_logger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once at startup (before yield) and once at shutdown (after yield).
    Use this for: creating directories, connecting to DBs, loading ML models.
    """
    setup_logging()  # must be first — all subsequent log calls depend on this

    # Pre-flight checks: Tesseract binary, writable directories.
    # Logs warnings for anything missing; never raises — server starts regardless.
    run_startup_checks()

    # Load the spaCy model once — blocks until ready, then held in memory.
    # Returns False (not an error) if spaCy/model is missing → regex-only mode.
    nlp_ready = load_nlp()

    logger.info(
        "startup_complete",
        extra={
            "app": settings.app_name,
            "upload_dir": str(settings.upload_path),
            "output_dir": str(settings.output_path),
            "max_file_mb": settings.max_file_size_mb,
            "nlp_ready": nlp_ready,
            "spacy_model": settings.spacy_model or "disabled",
        },
    )

    yield  # ← server is live and handling requests between here and shutdown

    logger.info("shutdown", extra={"app": settings.app_name})


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    description="Upload PDFs, images, and DOCX files — get extracted text and a preview image.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow any origin so frontends and API tools (Swagger, Postman) can
# reach the API without browser blocking.  Restrict origins in production by
# setting CORS_ORIGINS in .env (comma-separated list).
app.add_middleware(
    CORSMiddleware,
    # Parse CORS_ORIGINS env var: "*" → allow all, or "https://a.vercel.app,https://b.com"
    allow_origins=["*"] if settings.cors_origins.strip() == "*"
                  else [o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=False,   # must stay False when allow_origins includes "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve the outputs/ folder at /outputs so preview URLs resolve to real files
app.mount("/outputs", StaticFiles(directory=settings.output_dir), name="outputs")

# Register the document upload router (prefix: /documents)
app.include_router(document_router)

# Register the extraction router (prefix: /documents, tag: extraction)
app.include_router(extraction_router)


# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
async def health_check():
    """Quick liveness probe — returns 200 if the server is running."""
    return {
        "status": "ok",
        "app": settings.app_name,
        "max_file_size_mb": settings.max_file_size_mb,
        "allowed_types": settings.allowed_mime_types,
        "nlp_model": settings.spacy_model or "disabled",
        "nlp_ready": is_nlp_available(),
    }

