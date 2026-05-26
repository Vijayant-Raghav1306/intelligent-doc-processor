#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# build_render.sh — Legacy Render build script (SUPERSEDED by Docker)
#
# STATUS: This script was used when render.yaml had `runtime: python`.
#         We have since switched to `env: docker` in render.yaml.
#         Render now builds from the Dockerfile — this script is no longer
#         called by Render automatically.
#
# STILL USEFUL FOR:
#   • Testing the dependency install steps locally on a Linux machine
#   • CI pipeline (GitHub Actions, etc.) if you want a non-Docker pipeline
#   • Reference: shows exactly what the Dockerfile does, step by step
#
# To test locally on Linux/macOS:
#   bash build_render.sh
# ─────────────────────────────────────────────────────────────────────────────

set -e   # exit immediately on any error

echo "==> Installing system packages (requires sudo or root)..."
apt-get update -qq
apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    libgl1 \
    libglib2.0-0

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
