#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# build.sh — Render build script (alternative to inline buildCommand)
#
# Used automatically by render.yaml via:   buildCommand: ./build.sh
# Can also run locally for testing:        bash build.sh
#
# Render build containers run as root with network access, so apt-get works.
# ─────────────────────────────────────────────────────────────────────────────

set -e   # exit immediately on any error — fail fast during build

echo "==> Installing system packages..."
apt-get update -qq
apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev

echo "==> Verifying Tesseract install..."
tesseract --version

echo "==> Installing Python dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt

echo "==> Downloading spaCy model (en_core_web_sm)..."
python -m spacy download en_core_web_sm

echo "==> Verifying spaCy model..."
python -c "import spacy; nlp = spacy.load('en_core_web_sm'); print('spaCy OK:', nlp.meta['name'], nlp.meta['version'])"

echo "==> Build complete."
