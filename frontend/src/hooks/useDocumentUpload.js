/*
 * hooks/useDocumentUpload.js — custom React hook for the upload pipeline.
 *
 * WHY a custom hook?
 *   A hook extracts stateful logic OUT of a component. The Upload page component
 *   becomes simple markup; all the state management lives here.
 *   You can also reuse this hook elsewhere without duplicating the logic.
 *
 * WHAT this hook manages:
 *   1. File validation (type, size)
 *   2. Two parallel API calls: uploadDocument + extractInvoice
 *   3. Upload progress percentage
 *   4. Processing states: idle → uploading → processing → complete | error
 *   5. Storing results so the Results page can read them
 *
 * USAGE:
 *   const { state, progress, uploadResult, extractionResult, error, process, reset } =
 *     useDocumentUpload();
 *
 *   state can be: "idle" | "uploading" | "processing" | "complete" | "error"
 */
import { useState, useCallback } from "react";
import { uploadDocument, extractInvoice } from "../services/api.js";

// Allowed MIME types (mirror the backend setting)
const ALLOWED_TYPES = [
  "application/pdf",
  "image/jpeg",
  "image/jpg",
  "image/png",
  "image/tiff",
  "image/webp",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];

const MAX_SIZE_MB = 10;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

export function useDocumentUpload() {
  // ── State ────────────────────────────────────────────────────────────────
  const [state, setState] = useState("idle");
  // "idle"       — waiting for user to pick a file
  // "uploading"  — file bytes are being sent to the server (shows progress bar)
  // "processing" — server is running OCR + extraction (shows spinner)
  // "complete"   — both API calls returned successfully
  // "error"      — one or both API calls failed

  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadResult, setUploadResult]     = useState(null);
  const [extractionResult, setExtractionResult] = useState(null);
  const [error, setError] = useState(null);

  // ── File validator ───────────────────────────────────────────────────────
  const validateFile = useCallback((file) => {
    if (!file) return "No file selected.";
    if (!ALLOWED_TYPES.includes(file.type)) {
      return `Unsupported file type: ${file.type || "unknown"}. Use PDF, JPEG, PNG, TIFF, WEBP, or DOCX.`;
    }
    if (file.size > MAX_SIZE_BYTES) {
      return `File is too large (${(file.size / 1_048_576).toFixed(1)} MB). Maximum is ${MAX_SIZE_MB} MB.`;
    }
    return null; // null = valid
  }, []);

  // ── Main process function ─────────────────────────────────────────────────
  const process = useCallback(async (file, password = "") => {
    // Validate before touching the server
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      setState("error");
      return;
    }

    setError(null);
    setUploadProgress(0);
    setState("uploading");

    try {
      // ── Phase 1: Upload ──────────────────────────────────────────────────
      // Send file to server. onUploadProgress tracks bytes transferred.
      // Both calls run concurrently with Promise.all — faster than sequential.
      // (The file is sent TWICE because each endpoint needs it independently.)
      const [uploadData, extractData] = await Promise.all([
        uploadDocument(file, password, (pct) => {
          setUploadProgress(pct);
          // Once upload hits 100%, switch to "processing" (OCR/extraction running)
          if (pct === 100) setState("processing");
        }),
        extractInvoice(file, password),
      ]);

      setUploadResult(uploadData);
      setExtractionResult(extractData);
      setState("complete");

    } catch (err) {
      setError(err.message || "An unexpected error occurred.");
      setState("error");
    }
  }, [validateFile]);

  // ── Reset to initial state ────────────────────────────────────────────────
  const reset = useCallback(() => {
    setState("idle");
    setUploadProgress(0);
    setUploadResult(null);
    setExtractionResult(null);
    setError(null);
  }, []);

  return {
    state,           // "idle" | "uploading" | "processing" | "complete" | "error"
    uploadProgress,  // 0-100 during upload phase
    uploadResult,    // DocumentResponse from /documents/upload
    extractionResult,// InvoiceExtractionResult from /documents/extract/invoice
    error,           // error message string or null
    process,         // fn(file, password?) → starts the pipeline
    reset,           // fn() → clears all state back to idle
    ALLOWED_TYPES,
    MAX_SIZE_MB,
  };
}
