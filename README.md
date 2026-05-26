# 📄 Intelligent Document Processor

A production-ready FastAPI backend that extracts structured data from invoices, PDFs, scanned images, and Word documents — combining OCR, NLP, and regex-based rules with confidence scoring.

> **Live demo:** _[Deploy to Render first, then paste the URL here]_
> **API docs:** `https://your-render-url.onrender.com/docs`

---

## What Does This Project Do?

You upload a document (PDF, image, or Word file). The system:

1. **Reads it** — extracts raw text using OCR if needed
2. **Understands it** — uses NLP + regex to find invoice fields
3. **Returns structured JSON** — with confidence scores for every field

```
You send:  An invoice PDF

You get:   {
             "fields": {
               "vendor_name":    "Acme Corp Ltd",
               "invoice_number": "INV-2024-001",
               "invoice_date":   "2024-01-15",
               "due_date":       "2024-02-14",
               "total_amount":   1456.78,
               "currency":       "INR"
             },
             "overall_confidence": 0.91,
             "extraction_warnings": []
           }
```

---

## Why Does This Project Exist?

Invoices, receipts, and contracts all carry the same information — but in a thousand different formats. This project shows how to build a **modular, extensible document AI pipeline** that handles that variation, starting with invoices and designed to grow toward any document type.

It was built as a learning project to demonstrate:
- Real-world FastAPI architecture
- OCR preprocessing with OpenCV
- Hybrid NLP + regex extraction
- Production-safe deployment on Render

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        CLIENT                                │
│        POST /documents/extract/invoice                       │
│              (PDF / Image / DOCX file)                       │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                      FastAPI Layer                           │
│         • File validation  • Size check  • CORS              │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│                    Document Router                           │
│           Reads magic bytes → picks the right loader         │
└──────────┬───────────────┬──────────────────┬───────────────┘
           │               │                  │
           ▼               ▼                  ▼
    ┌─────────────┐ ┌─────────────┐ ┌──────────────┐
    │  PDF Loader │ │Image Loader │ │  DOCX Loader │
    │             │ │             │ │              │
    │ pdfplumber  │ │   OpenCV    │ │ python-docx  │
    │ + PyMuPDF   │ │ (preprocess)│ │              │
    │ + OCR       │ │ + Tesseract │ │              │
    │ (for scans) │ │    (OCR)    │ │              │
    └──────┬──────┘ └──────┬──────┘ └──────┬───────┘
           └───────────────┴───────────────┘
                           │
                           │  raw text
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                   Extraction Layer                           │
│              InvoiceExtractor (Hybrid)                       │
│                                                              │
│  ┌───────────────────┐    ┌───────────────────┐             │
│  │  Regex Patterns   │    │    spaCy NLP       │             │
│  │                   │    │                   │             │
│  │  • Invoice No     │    │  • ORG entities   │             │
│  │  • Invoice Date   │    │  • DATE entities  │             │
│  │  • Due Date       │    │  • MONEY entities │             │
│  │  • Total Amount   │    │  • Proximity      │             │
│  │  • Currency       │    │    search         │             │
│  └────────┬──────────┘    └────────┬──────────┘             │
│           └──────────┬─────────────┘                        │
│                      │  fuse_confidence()                   │
│                      ▼                                       │
│           ┌────────────────────┐                            │
│           │  Confidence Fusion │                            │
│           │  + Field Validation│                            │
│           └────────────────────┘                            │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                  JSON Response                               │
│  fields  •  confidence  •  overall_confidence               │
│  extraction_warnings  •  raw_text_length                    │
└──────────────────────────────────────────────────────────────┘
```

---

## Features

| Feature | Details |
|---------|---------|
| 📄 **Multi-format support** | PDF (native + scanned), JPEG, PNG, TIFF, WEBP, DOCX |
| 🔍 **OCR pipeline** | OpenCV preprocessing (denoise, deskew, threshold) + Tesseract |
| 🧠 **Hybrid NLP extraction** | spaCy NER + regex patterns with confidence fusion |
| 📊 **Confidence scoring** | Per-field scores (0.0–1.0) + overall confidence |
| ⚠️ **Extraction warnings** | Non-fatal issues surfaced in response (e.g. date inconsistencies) |
| 🔒 **Encrypted PDFs** | Password-protected PDF support |
| 🖼️ **Document previews** | First-page preview image generated on upload |
| 📝 **Structured logging** | Module-level loggers with per-field extras |
| ✅ **232 tests** | Unit + integration tests, zero mocks for file I/O |
| 🚀 **Render-ready** | One-click deploy with `render.yaml` |
| 🛡️ **Graceful degradation** | No Tesseract → PDF/DOCX still works. No spaCy → regex-only mode |

---

## Tech Stack

Here's every major technology used, explained simply:

### FastAPI
The web framework. Think of it like Express.js but for Python. It automatically generates interactive API documentation at `/docs`, handles file uploads, validates request data, and is fast enough for production.

### OpenCV
A computer vision library. We use it to pre-process scanned images before OCR: converting to grayscale, removing noise, straightening tilted pages (deskewing), and increasing contrast. Better image → better OCR accuracy.

### Tesseract
Google's open-source OCR (Optical Character Recognition) engine. It reads images and converts them to text. We point it at preprocessed images from OpenCV.

### spaCy
An industrial-strength NLP library. It reads text and identifies *named entities* — recognizing that "Acme Corp Ltd" is a company (ORG), "15 January 2024" is a date (DATE), and "$1,234.56" is money (MONEY). We use this to extract invoice fields that don't have explicit labels.

### pdfplumber
Extracts native (selectable) text from PDFs. When a PDF was created digitally, the text is embedded directly — pdfplumber gets it accurately without OCR.

### PyMuPDF (fitz)
Renders PDF pages as high-resolution images. Used for password-protected PDFs and for converting scanned PDF pages to images before OCR.

### Pillow (PIL)
Python's standard image library. Used for image format conversion, resizing, and generating preview thumbnails.

### pytest
The testing framework. We have 232 tests across unit tests (testing individual functions in isolation) and integration tests (testing the full HTTP request/response cycle with a real FastAPI server).

---

## Project Structure

```
intelligent-doc-processor/
│
├── app/
│   ├── main.py                    # FastAPI app, lifespan, startup
│   │
│   ├── core/
│   │   ├── config.py              # All settings (loaded from .env)
│   │   ├── logging_config.py      # Structured logging setup
│   │   └── startup.py             # Pre-flight checks (Tesseract, dirs)
│   │
│   ├── api/routes/
│   │   ├── document.py            # POST /documents/upload
│   │   └── extraction.py          # POST /documents/extract/invoice
│   │
│   ├── services/                  # Document loading layer
│   │   ├── base_loader.py         # Abstract base class for all loaders
│   │   ├── document_router.py     # filetype detection → loader selection
│   │   ├── pdf_loader.py          # PDF: pdfplumber + PyMuPDF + OCR
│   │   ├── image_loader.py        # Images: OpenCV preprocessing + Tesseract
│   │   └── docx_loader.py         # Word: python-docx
│   │
│   └── extraction/                # Information extraction layer
│       ├── base_extractor.py      # Abstract base class for all extractors
│       ├── schemas.py             # Pydantic response models
│       ├── patterns.py            # Regex pattern library with confidence scores
│       ├── normalizers.py         # Date, amount, currency normalization
│       ├── nlp_service.py         # spaCy model loading (singleton)
│       ├── nlp_utils.py           # NLP helper functions
│       └── invoice_extractor.py   # Hybrid extraction logic
│
├── tests/
│   ├── conftest.py                # Shared fixtures (programmatic test files)
│   ├── unit/
│   │   ├── test_pdf_loader.py
│   │   ├── test_image_loader.py
│   │   ├── test_docx_loader.py
│   │   ├── test_normalizers.py
│   │   ├── test_invoice_extractor.py
│   │   └── test_nlp_utils.py
│   └── integration/
│       ├── test_upload_endpoint.py
│       └── test_extraction_endpoint.py
│
├── .env.example                   # Environment variable template
├── render.yaml                    # Render deployment config
├── build.sh                       # Render build script
└── requirements.txt
```

---

## How It Works — Request Lifecycle

```
Step 1: You POST a file to /documents/extract/invoice

Step 2: FastAPI validates the request (file present? size OK?)

Step 3: The file is saved with a UUID name (security: prevents path traversal)
        e.g.  a3f9bc12...pdf

Step 4: Document Router reads the first few bytes (magic bytes) to detect
        the real file type — NOT trusting the filename extension.
        .pdf → PdfLoader
        .jpg → ImageLoader
        .docx → DocxLoader

Step 5: The loader extracts raw text:
        PDF  → pdfplumber reads native text; falls back to OCR for scanned pages
        Image → OpenCV preprocesses → Tesseract OCR
        DOCX → python-docx reads paragraphs and tables

Step 6: InvoiceExtractor receives the raw text.
        It runs spaCy (nlp(text)) once to get a Doc object,
        then runs 7 field extractors in parallel — all sharing the same Doc.

Step 7: Each field extractor:
          a) Tries regex patterns (deterministic, labeled matches)
          b) Tries NLP entities (probabilistic, unlabeled matches)
          c) Calls fuse_confidence() to merge both results

Step 8: validate_field_consistency() cross-checks:
          - Is due_date after invoice_date?
          - Does total_amount ≈ sum of line items?

Step 9: The temp file is deleted (always, even on errors)

Step 10: JSON response is returned with fields + confidence scores
```

---

## Local Setup

### Prerequisites

- Python 3.10 or higher
- [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) (for image/scanned PDF support)
- Git

### Step 1 — Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/intelligent-doc-processor.git
cd intelligent-doc-processor
```

### Step 2 — Create a virtual environment

```bash
# Create it
python -m venv venv

# Activate it
# Windows:
venv\Scripts\activate
# macOS / Linux:
source venv/bin/activate
```

You'll know it worked when you see `(venv)` at the start of your terminal prompt.

### Step 3 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Install the spaCy language model

```bash
python -m spacy download en_core_web_sm
```

This downloads a ~12MB English NLP model. Only needed once.

### Step 5 — Configure environment variables

```bash
# Copy the template
cp .env.example .env   # macOS/Linux
copy .env.example .env # Windows
```

Open `.env` and set `TESSERACT_CMD` to your Tesseract path:

```bash
# macOS (after `brew install tesseract`):
TESSERACT_CMD=tesseract

# Windows — find your actual path:
TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
```

### Step 6 — Run the server

```bash
uvicorn app.main:app --reload
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) — you'll see the interactive API.

---

## API Endpoints

### `GET /health`
Liveness probe. Returns server status + NLP readiness.

```bash
curl http://localhost:8000/health
```
```json
{
  "status": "ok",
  "app": "Intelligent Doc Processor",
  "nlp_ready": true,
  "nlp_model": "en_core_web_sm"
}
```

---

### `POST /documents/upload`
Upload a document to extract raw text and generate a preview image.

```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@invoice.pdf"
```
```json
{
  "filename": "invoice.pdf",
  "file_type": "application/pdf",
  "page_count": 1,
  "char_count": 342,
  "text": "Acme Corp Ltd\nInvoice No: INV-2024-001\n...",
  "preview_url": "/outputs/a3f9bc12.jpg",
  "metadata": { "pages": 1, "encrypted": false }
}
```

**Password-protected PDFs:**
```bash
curl -X POST http://localhost:8000/documents/upload \
  -F "file=@locked.pdf" \
  -F "password=mypassword"
```

---

### `POST /documents/extract/invoice`
Upload a document and extract structured invoice fields.

```bash
curl -X POST http://localhost:8000/documents/extract/invoice \
  -F "file=@invoice.pdf"
```
```json
{
  "document_type": "invoice",
  "fields": {
    "vendor_name":    "Acme Corp Ltd",
    "invoice_number": "INV-2024-001",
    "invoice_date":   "2024-01-15",
    "due_date":       "2024-02-14",
    "total_amount":   1456.78,
    "currency":       "INR",
    "line_items": [
      { "description": "Widget A", "quantity": 2.0, "unit_price": 500.0, "amount": 1000.0 },
      { "description": "Widget B", "quantity": 1.0, "unit_price": 234.56, "amount": 234.56 }
    ]
  },
  "confidence": {
    "vendor_name":    0.80,
    "invoice_number": 0.95,
    "invoice_date":   0.95,
    "due_date":       0.95,
    "total_amount":   0.97,
    "currency":       0.90
  },
  "overall_confidence": 0.92,
  "extraction_warnings": [],
  "raw_text_length": 455
}
```

**Confidence score guide:**
| Score | Meaning |
|-------|---------|
| 0.90–1.0 | Strong labeled match (e.g. "Invoice Date: 15/01/2024") |
| 0.75–0.89 | Good match or regex+NLP agreement |
| 0.50–0.74 | Heuristic / NLP-only match |
| 0.0 | Field not found |

---

## Running Tests

```bash
# Run all 232 tests
pytest

# Run with verbose output
pytest -v

# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run a specific test file
pytest tests/unit/test_normalizers.py -v

# Run with coverage report
pip install pytest-cov
pytest --cov=app --cov-report=term-missing
```

**Test design notes:**
- Test files are created **programmatically** at runtime using PyMuPDF, python-docx, and Pillow — no binary blobs committed to git
- Integration tests spin up a real FastAPI server using `TestClient` (no mocking)
- OCR tests are skipped if Tesseract is not installed (`@requires_tesseract` marker)
- spaCy tests are skipped if the model is not installed (`@requires_spacy` marker)

---

## Deployment (Render)

### Prerequisites
- GitHub account
- Render account — [render.com](https://render.com) (free tier available)

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit: Intelligent Document Processor"
git remote add origin https://github.com/YOUR_USERNAME/intelligent-doc-processor.git
git push -u origin main
```

### Step 2 — Create a new Web Service on Render

1. Go to [dashboard.render.com](https://dashboard.render.com)
2. Click **New** → **Web Service**
3. Click **Connect a repository** → select your GitHub repo
4. Render detects `render.yaml` automatically and pre-fills all settings

### Step 3 — Verify settings (Render will pre-fill from render.yaml)

| Setting | Value |
|---------|-------|
| **Runtime** | Python 3 |
| **Build Command** | `apt-get install -y tesseract-ocr libtesseract-dev && pip install -r requirements.txt && python -m spacy download en_core_web_sm` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1` |
| **Health Check Path** | `/health` |

### Step 4 — Set environment variables

In the Render dashboard → **Environment** tab, add:

| Variable | Value |
|----------|-------|
| `TESSERACT_CMD` | `tesseract` |
| `SPACY_MODEL` | `en_core_web_sm` |
| `MAX_FILE_SIZE_MB` | `10` |

### Step 5 — Deploy

Click **Create Web Service**. Render will:
1. Clone your repo
2. Run the build command (~2-3 minutes)
3. Start the server
4. Run the health check on `/health`
5. Mark the deploy as live ✅

### Your live URL
```
https://intelligent-doc-processor.onrender.com/docs
```

### Important: Free tier behaviour
The free tier **sleeps after 15 minutes of inactivity**. The first request after sleep takes ~5-10 extra seconds (the server restarts and reloads the spaCy model). Subsequent requests are fast. Upgrade to the **Starter plan** ($7/month) for always-on.

### Debugging a failed deploy

If the deploy fails:
1. Click **Logs** in the Render dashboard
2. Look for the first `ERROR` line
3. Common causes:

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: spacy` | `pip install spacy` missing from build command |
| `OSError: [E050] Can't find model 'en_core_web_sm'` | Add `python -m spacy download en_core_web_sm` to build command |
| `tesseract: command not found` | Add `apt-get install -y tesseract-ocr` to build command |
| `Address already in use` | Check start command uses `$PORT` not a hardcoded port |
| `Health check failed` | Your `/health` route returned non-200 — check startup logs |

---

## Future Improvements

This project is intentionally built in phases to show a progression from basic regex to modern document AI:

### Near-term (Phase 5–6)
- **Custom NER training** — train spaCy on real labeled invoices. "INV-2024-001" would become a proper `INVOICE_NUM` entity, not left to regex.
- **Receipt extractor** — reuse the same architecture (`BaseExtractor` → `ReceiptExtractor`), different patterns.
- **Multi-page invoice support** — merge context across pages before extraction.

### Medium-term (Phase 7–8)
- **LayoutLM integration** — Microsoft's transformer model that understands both text and bounding box positions. Dramatically better for tables and multi-column layouts. Today we can't tell "Total" in a footer from "Total" in a header — LayoutLM can.
- **Cloud storage for previews** — write preview images to S3/GCS instead of local filesystem. Necessary for multi-worker production deployments.
- **Human-in-the-loop queue** — documents with `overall_confidence < 0.60` are queued for human review instead of being returned directly.

### Long-term (Phase 9+)
- **Donut / Nougat** — document understanding models that operate directly on page images without a separate OCR step.
- **Multilingual support** — spaCy's `xx_ent_wiki_sm` model handles 7 languages. Full multilingual needs a multilingual OCR model.
- **Async job queue** — for large batches of invoices, move to a queue-based architecture (Celery + Redis) instead of blocking HTTP requests.

---

## Engineering Highlights

If you're reviewing this project as a hiring signal, here are the decisions worth noting:

**1. Graceful degradation as a first-class design goal**
The system has four capability levels: full (OCR + NLP), NLP-only, regex-only, and file-read-only. Each level degrades cleanly. The API always returns a valid response — never a 500 caused by a missing binary.

**2. Confidence fusion instead of winner-takes-all**
When regex and NLP agree, confidence increases. When they disagree, the deterministic regex wins but a warning is emitted. This is more useful than blindly trusting either system.

**3. No mocking in integration tests**
Test files are built programmatically at runtime using the same libraries the server uses (PyMuPDF, python-docx, Pillow). This means tests catch real integration bugs, not mocked fantasies.

**4. `_AMOUNT_VAL` regex handles 5 numeric formats**
US (`1,234.56`), European (`1.234,56`), Indian (`1,23,456.78`), space-separated (`1 234.56`), and K/M suffixes (`1.5K`) — all parsed by a single regex + normalizer combination.

**5. `BaseExtractor` / `BaseLoader` ABC pattern**
Adding a new document type (receipts, medical forms) requires writing one loader class and one extractor class. Zero changes to routing, API, or logging.

---

## License

MIT — see [LICENSE](LICENSE) for details.

---

<details>
<summary>📊 Test coverage summary</summary>

| Module | Tests |
|--------|-------|
| `test_pdf_loader.py` | 18 |
| `test_image_loader.py` | 14 |
| `test_docx_loader.py` | 14 |
| `test_normalizers.py` | 82 |
| `test_invoice_extractor.py` | 37 |
| `test_nlp_utils.py` | 32 |
| `test_upload_endpoint.py` | 19 |
| `test_extraction_endpoint.py` | 15 |
| **Total** | **232** |

</details>
