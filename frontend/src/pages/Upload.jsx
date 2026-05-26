/*
 * pages/Upload.jsx — document upload page.
 *
 * Flow:
 *   1. User drops or selects a file (DropZone component)
 *   2. User clicks "Process Document"
 *   3. useDocumentUpload.process() is called → starts API calls
 *   4. UploadProgress component shows during uploading/processing
 *   5. On success → navigate to /results with data passed via state
 *   6. On error → show error message inline
 *
 * State passing to Results page:
 *   React Router allows passing arbitrary data via navigate(path, { state: {...} }).
 *   The Results page reads it back with useLocation().state.
 *   The data lives in memory only — a page refresh on /results clears it
 *   (user would need to re-upload).
 */
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { AlertCircle, ArrowRight, RefreshCw } from "lucide-react";
import { useDocumentUpload } from "../hooks/useDocumentUpload.js";
import DropZone from "../components/upload/DropZone.jsx";
import UploadProgress from "../components/upload/UploadProgress.jsx";

export default function Upload() {
  const navigate = useNavigate();
  const [selectedFile, setSelectedFile] = useState(null);
  const [password, setPassword]         = useState("");

  const {
    state,
    uploadProgress,
    uploadResult,
    extractionResult,
    error,
    process,
    reset,
    MAX_SIZE_MB,
  } = useDocumentUpload();

  // ── Navigate to Results when both API calls complete ──────────────────────
  useEffect(() => {
    if (state === "complete" && uploadResult && extractionResult) {
      navigate("/results", {
        state: { uploadResult, extractionResult },
        replace: false,  // keep /upload in browser history (back button works)
      });
    }
  }, [state, uploadResult, extractionResult, navigate]);

  // ── Handlers ──────────────────────────────────────────────────────────────
  const handleFileSelect = (file, pwd) => {
    setSelectedFile(file);
    setPassword(pwd || "");
    // Clear any previous error when a new file is selected
    if (error) reset();
  };

  const handleProcess = () => {
    if (selectedFile) process(selectedFile, password);
  };

  const handleReset = () => {
    setSelectedFile(null);
    setPassword("");
    reset();
  };

  // ── Render ────────────────────────────────────────────────────────────────
  const isActive = state === "uploading" || state === "processing";

  return (
    <div className="max-w-xl mx-auto space-y-6">
      {/* Page heading */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Upload Document</h1>
        <p className="mt-1 text-gray-500 text-sm">
          Drop your invoice, receipt, or PDF to extract structured fields.
        </p>
      </div>

      {/* Show progress or drop zone */}
      {isActive ? (
        <UploadProgress state={state} uploadProgress={uploadProgress} />
      ) : (
        <div className="card">
          <DropZone
            onFileSelect={handleFileSelect}
            selectedFile={selectedFile}
            maxSizeMB={MAX_SIZE_MB}
          />

          {/* Error banner */}
          {error && (
            <div className="mt-4 flex items-start gap-3 p-4 bg-rose-50 rounded-xl
                           ring-1 ring-rose-200 text-sm text-rose-800">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-rose-500" />
              <div>
                <p className="font-medium">Processing failed</p>
                <p className="mt-0.5 text-rose-700">{error}</p>
              </div>
            </div>
          )}

          {/* Action buttons */}
          <div className="mt-5 flex gap-3">
            <button
              onClick={handleProcess}
              disabled={!selectedFile}
              className="btn-primary flex-1 justify-center py-3"
            >
              Process Document
              <ArrowRight className="w-4 h-4" />
            </button>

            {(selectedFile || error) && (
              <button onClick={handleReset} className="btn-secondary px-4" title="Reset">
                <RefreshCw className="w-4 h-4" />
              </button>
            )}
          </div>

          {/* Help text */}
          {!selectedFile && !error && (
            <p className="mt-4 text-center text-xs text-gray-400">
              Processing sends your document to the backend for OCR + NLP extraction.
              Files are deleted from the server after processing.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
