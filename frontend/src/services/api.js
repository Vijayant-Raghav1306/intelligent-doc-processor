/*
 * services/api.js — the ONLY place in the app that talks to the backend.
 *
 * WHY a service layer?
 *   If you scatter fetch() calls across 10 components, changing the base URL
 *   or adding auth headers means editing 10 files. The service layer is one
 *   file: change here, fixed everywhere.
 *
 * HOW it works:
 *   1. axios.create() builds a pre-configured HTTP client with a base URL
 *      and default timeout. All requests made via this client inherit those.
 *   2. VITE_API_URL is read from .env.local at build time by Vite.
 *      In production: set it to your Render URL.
 *      In development: leave it blank; the vite.config.js proxy handles routing.
 *   3. Each exported function wraps one API endpoint. Components never
 *      construct URLs or FormData themselves.
 *
 * CORS note:
 *   The FastAPI backend has CORS configured to allow all origins ("*").
 *   In production you should restrict this to your Vercel domain.
 */
import axios from "axios";

// In development, VITE_API_URL is empty and the Vite proxy handles routing.
// In production (Vercel), VITE_API_URL = "https://your-app.onrender.com"
const BASE_URL = import.meta.env.VITE_API_URL || "";

const client = axios.create({
  baseURL: BASE_URL,
  // OCR + NLP extraction can take up to 60 seconds on free-tier Render
  // (Render spins down after 15 min inactivity; first request is slow).
  timeout: 90_000,
});

// ── Request interceptor: log all outgoing requests (development only) ─────────
client.interceptors.request.use((config) => {
  if (import.meta.env.DEV) {
    console.debug(`[API] ${config.method?.toUpperCase()} ${config.url}`);
  }
  return config;
});

// ── Response interceptor: normalize errors into readable messages ─────────────
client.interceptors.response.use(
  (response) => response,
  (error) => {
    // axios wraps HTTP errors in error.response
    // We extract the most useful message from FastAPI error shapes
    const detail = error.response?.data?.detail;
    const status = error.response?.status;

    let message;
    if (typeof detail === "string") {
      message = detail;
    } else if (Array.isArray(detail)) {
      // Pydantic validation errors come as an array of objects
      message = detail.map((e) => e.msg || JSON.stringify(e)).join("; ");
    } else if (!error.response) {
      message = "Cannot reach the server. Is the backend running?";
    } else {
      message = `Server error (HTTP ${status})`;
    }

    // Replace the error message with our clean version
    error.message = message;
    return Promise.reject(error);
  }
);


// ── Exported API functions ─────────────────────────────────────────────────────

/**
 * POST /documents/upload
 *
 * Uploads a document file and returns:
 *   - filename      string   original filename
 *   - file_type     string   detected MIME type
 *   - page_count    number
 *   - char_count    number
 *   - text          string   full extracted text
 *   - preview_url   string   relative URL e.g. "/outputs/abc_preview.jpg"
 *   - metadata      object   loader-specific extras
 *
 * @param {File}     file             The File object from the file picker
 * @param {string}   password         Password for encrypted PDFs (or "")
 * @param {Function} onUploadProgress Called with percent 0-100 during upload
 */
export async function uploadDocument(file, password = "", onUploadProgress) {
  const formData = new FormData();
  formData.append("file", file);
  if (password) formData.append("password", password);

  const response = await client.post("/documents/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (evt) => {
      if (evt.total) {
        const pct = Math.round((evt.loaded * 100) / evt.total);
        onUploadProgress?.(pct);
      }
    },
  });

  return response.data; // DocumentResponse
}


/**
 * POST /documents/extract/invoice
 *
 * Uploads a document and returns structured invoice extraction:
 *   - document_type        string    always "invoice"
 *   - fields               object    {vendor_name, invoice_number, invoice_date,
 *                                     due_date, total_amount, currency, line_items}
 *   - confidence           object    per-field confidence 0.0 to 1.0
 *   - overall_confidence   number    mean of non-zero confidence scores
 *   - extraction_warnings  string[]  non-fatal issues encountered
 *   - raw_text_length      number    chars passed to extractor
 *
 * @param {File}   file      The same File object passed to uploadDocument
 * @param {string} password  Password for encrypted PDFs (or "")
 */
export async function extractInvoice(file, password = "") {
  const formData = new FormData();
  formData.append("file", file);
  if (password) formData.append("password", password);

  const response = await client.post("/documents/extract/invoice", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data; // InvoiceExtractionResult
}


/**
 * GET /health
 *
 * Quick connectivity check. Returns:
 *   { status: "ok", app: string, nlp_ready: bool, ... }
 *
 * Used by the Home page to show backend status.
 */
export async function checkHealth() {
  const response = await client.get("/health", { timeout: 10_000 });
  return response.data;
}
