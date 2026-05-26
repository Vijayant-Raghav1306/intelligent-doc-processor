# ─────────────────────────────────────────────────────────────────────────────
# Dockerfile — Intelligent Document Processor
#
# Base image : python:3.11-slim  (Debian Bookworm, ~45 MB before layers)
# Final size : ~900 MB (NumPy + OpenCV + spaCy + Tesseract are large)
#
# LAYER CACHING STRATEGY (read this once, save hours of debugging):
#
#   Docker rebuilds from the FIRST changed layer downward.
#   We deliberately order instructions from "rarely changes" → "often changes":
#
#   1. FROM           — never changes
#   2. ENV            — almost never changes
#   3. apt-get        — changes only if you add a new system package
#   4. pip install    — changes when requirements.txt changes
#   5. spacy download — changes when spaCy version changes
#   6. COPY app/      — changes every time you edit Python code ← most frequent
#
#   Because step 6 is LAST, editing app/main.py only invalidates layer 6.
#   Steps 1-5 are served from cache — the rebuild takes seconds, not minutes.
# ─────────────────────────────────────────────────────────────────────────────


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  LAYER 1 — Base image
# ║
# ║  python:3.11-slim  =  official Python image on Debian Bookworm (minimal).
# ║  "slim" removes manpages, locale data, and C headers → smaller image.
# ║  spaCy 3.8 officially supports Python 3.9–3.12; 3.11 is the sweet spot.
# ╚══════════════════════════════════════════════════════════════════════════════
FROM python:3.11-slim


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  LAYER 2 — Environment variables (baked into the image)
# ║
# ║  PYTHONDONTWRITEBYTECODE=1  → no .pyc files (saves disk space)
# ║  PYTHONUNBUFFERED=1         → print() / logger output appears immediately
# ║                               in `docker logs` and Render log stream
# ║  PIP_NO_CACHE_DIR=1         → pip doesn't cache wheels inside the image
# ║                               (saves ~100 MB from the final image size)
# ║  PIP_DISABLE_PIP_VERSION_CHECK=1  → silences the "pip upgrade" banner
# ╚══════════════════════════════════════════════════════════════════════════════
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  LAYER 3 — System packages (THIS is why we switched to Docker)
# ║
# ║  In Render's standard Python build environment, apt-get is blocked.
# ║  Here, we are root inside OUR OWN container build — apt-get works freely.
# ║
# ║  tesseract-ocr      → the Tesseract OCR binary  (pytesseract calls this)
# ║  libtesseract-dev   → C headers for Tesseract  (needed by some pip wheels)
# ║  libgl1             → OpenGL runtime library    (OpenCV links against it
# ║                        even in headless mode on some Debian versions)
# ║  libglib2.0-0       → GLib runtime             (OpenCV dependency)
# ║
# ║  `--no-install-recommends` skips optional extras → smaller image.
# ║  `rm -rf /var/lib/apt/lists/*` deletes the package index after install
# ║   (it's only needed during apt-get, not at runtime → saves ~40 MB).
# ╚══════════════════════════════════════════════════════════════════════════════
RUN apt-get update -qq && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        libtesseract-dev \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  LAYER 4 — Working directory
# ║
# ║  All subsequent COPY / RUN commands happen relative to /app.
# ║  Docker creates /app automatically if it doesn't exist.
# ╚══════════════════════════════════════════════════════════════════════════════
WORKDIR /app


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  LAYER 5 — Python dependencies
# ║
# ║  IMPORTANT: We copy requirements.txt BEFORE copying app code.
# ║  Why? Because pip install is slow (~2-5 min). If we copied all of app/
# ║  first, editing a single .py file would invalidate the pip install layer
# ║  and force a full reinstall on every build. By separating them:
# ║    - Edit app code       → only LAYER 7 rebuilds (fast)
# ║    - Edit requirements   → LAYER 5 + 6 + 7 rebuild (pip re-runs once)
# ╚══════════════════════════════════════════════════════════════════════════════
COPY requirements.txt .
RUN pip install --upgrade pip --quiet && \
    pip install -r requirements.txt


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  LAYER 6 — spaCy language model
# ║
# ║  en_core_web_sm (~12 MB) — English NER model for vendor/date/amount extraction.
# ║  Downloaded from GitHub releases directly into the container image.
# ║  This layer is cached separately from pip install so that adding a new
# ║  Python package doesn't force a re-download of the model.
# ╚══════════════════════════════════════════════════════════════════════════════
RUN python -m spacy download en_core_web_sm && \
    python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('spaCy model OK:', nlp.meta['name'])"


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  LAYER 7 — Application code
# ║
# ║  Copied LAST because this is what you edit most often.
# ║  Only this layer rebuilds when you change Python source files.
# ╚══════════════════════════════════════════════════════════════════════════════
COPY app/ ./app/


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  LAYER 8 — Non-root user (security best practice)
# ║
# ║  Running as root inside a container is a security risk. If an attacker
# ║  escapes the container, they'd have root on the host. We create a
# ║  dedicated user "appuser" and switch to it for the running process.
# ║
# ║  --no-log-init   → don't write to /var/log/lastlog (saves space)
# ║  chown -R        → give appuser ownership of everything in /app
# ║                    (required so the app can write to uploads/ outputs/)
# ╚══════════════════════════════════════════════════════════════════════════════
RUN useradd --create-home --no-log-init appuser && \
    mkdir -p uploads outputs && \
    chown -R appuser:appuser /app

USER appuser


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  EXPOSE — documentation hint
# ║
# ║  This does NOT open a port. It's a label that says "this container
# ║  expects to receive traffic on port 8000." Render reads this metadata
# ║  but ultimately uses the $PORT env var it injects at runtime.
# ╚══════════════════════════════════════════════════════════════════════════════
EXPOSE 8000


# ╔══════════════════════════════════════════════════════════════════════════════
# ║  CMD — the command that runs when the container starts
# ║
# ║  We use `sh -c "..."` (shell form) instead of exec form ["uvicorn", ...]
# ║  because we need shell variable expansion to read $PORT.
# ║
# ║  ${PORT:-8000} means: use $PORT if it's set, otherwise default to 8000.
# ║    - On Render: PORT is set to Render's chosen port (e.g., 10000)
# ║    - Locally:   PORT is not set → defaults to 8000
# ║
# ║  --host 0.0.0.0  → accept connections from any IP (not just localhost)
# ║  --workers 1     → free tier has 512 MB RAM; 1 worker is safe
# ║                    increase to 2-4 on paid plans
# ╚══════════════════════════════════════════════════════════════════════════════
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
