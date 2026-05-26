/*
 * pages/Results.jsx — shows extraction results after document processing.
 *
 * DATA SOURCE:
 *   This page reads data from React Router location.state, which was passed
 *   by Upload.jsx via: navigate("/results", { state: { uploadResult, extractionResult } })
 *
 *   If location.state is null (e.g., user navigates to /results directly via URL),
 *   we show a "no results" state and redirect them to upload.
 *
 * LAYOUT (two-column on desktop, stacked on mobile):
 *   Left:  Document preview image + overall confidence + raw text
 *   Right: Extracted fields (each with confidence bar + source tag) + line items
 *
 * DATA SHAPE (from schemas.py):
 *   extractionResult = {
 *     document_type: "invoice",
 *     fields: {
 *       vendor_name, invoice_number, invoice_date, due_date,
 *       total_amount, currency, line_items
 *     },
 *     confidence: {
 *       vendor_name, invoice_number, invoice_date, due_date,
 *       total_amount, currency
 *     },
 *     overall_confidence: 0.0 to 1.0,
 *     extraction_warnings: string[],
 *     raw_text_length: number,
 *   }
 *
 *   uploadResult = {
 *     filename, file_type, page_count, char_count,
 *     text,          // full raw text
 *     preview_url,   // "/outputs/abc_preview.jpg" — relative URL
 *     metadata,
 *   }
 */
import { useLocation, useNavigate } from "react-router-dom";
import { Upload, AlertTriangle, CheckCircle, Award, FileText, Clock } from "lucide-react";
import FieldCard from "../components/results/FieldCard.jsx";
import LineItemsTable from "../components/results/LineItemsTable.jsx";
import RawTextPanel from "../components/results/RawTextPanel.jsx";
import ProgressBar from "../components/ui/ProgressBar.jsx";
import Badge from "../components/ui/Badge.jsx";
import { formatConfidence, confidenceColors, formatDate } from "../utils/formatters.js";

// The 6 fields from InvoiceFields (in display order)
const FIELD_NAMES = [
  "vendor_name",
  "invoice_number",
  "invoice_date",
  "due_date",
  "total_amount",
  "currency",
];

// Build the full image URL from a relative preview_url like "/outputs/abc.jpg"
// In development the Vite proxy serves it from localhost:8000
// In production VITE_API_URL is the Render base URL
function buildPreviewUrl(relativeUrl) {
  if (!relativeUrl) return null;
  const base = import.meta.env.VITE_API_URL || "";
  return `${base}${relativeUrl}`;
}

export default function Results() {
  const location = useLocation();
  const navigate = useNavigate();

  // ── Guard: no data → redirect to upload ───────────────────────────────────
  if (!location.state?.uploadResult || !location.state?.extractionResult) {
    return (
      <div className="max-w-md mx-auto text-center py-24 space-y-4">
        <div className="w-16 h-16 bg-gray-100 rounded-2xl flex items-center justify-center mx-auto">
          <FileText className="w-8 h-8 text-gray-400" />
        </div>
        <h2 className="text-lg font-semibold text-gray-900">No results to display</h2>
        <p className="text-sm text-gray-500">Upload a document first to see extraction results here.</p>
        <button onClick={() => navigate("/upload")} className="btn-primary mx-auto mt-2">
          <Upload className="w-4 h-4" />
          Upload a document
        </button>
      </div>
    );
  }

  const { uploadResult, extractionResult } = location.state;
  const { fields, confidence, overall_confidence, extraction_warnings } = extractionResult;
  const previewUrl = buildPreviewUrl(uploadResult.preview_url);

  // Overall confidence display
  const overallColors = confidenceColors(overall_confidence);
  const overallPct    = Math.round(overall_confidence * 100);

  return (
    <div className="space-y-6">

      {/* ── Page header ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Extraction Results</h1>
          <p className="mt-0.5 text-sm text-gray-500">
            {uploadResult.filename} &bull; {uploadResult.page_count} page{uploadResult.page_count !== 1 ? "s" : ""}
            &bull; {uploadResult.char_count?.toLocaleString()} chars extracted
          </p>
        </div>
        <button
          onClick={() => navigate("/upload")}
          className="btn-secondary text-sm"
        >
          <Upload className="w-4 h-4" />
          Process Another
        </button>
      </div>

      {/* ── Warnings banner ─────────────────────────────────────────────── */}
      {extraction_warnings?.length > 0 && (
        <div className="flex items-start gap-3 p-4 bg-amber-50 rounded-xl ring-1 ring-amber-200">
          <AlertTriangle className="w-4 h-4 mt-0.5 flex-shrink-0 text-amber-500" />
          <div className="text-sm">
            <p className="font-medium text-amber-900">Extraction warnings</p>
            <ul className="mt-1 space-y-0.5 text-amber-800">
              {extraction_warnings.map((w, i) => (
                <li key={i}>{w}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* ── Main two-column layout ─────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">

        {/* ── LEFT COLUMN: Preview + Raw Text ───────────────────────────── */}
        <div className="lg:col-span-2 space-y-5">

          {/* Document preview image */}
          <div className="card p-4">
            <h2 className="section-heading">Document Preview</h2>
            {previewUrl ? (
              <img
                src={previewUrl}
                alt="Document preview"
                className="w-full rounded-lg border border-gray-200 shadow-sm object-contain max-h-96"
                onError={(e) => {
                  e.target.style.display = "none";
                  e.target.nextSibling.style.display = "flex";
                }}
              />
            ) : null}
            {/* Fallback when image fails to load */}
            <div className="hidden w-full h-48 bg-gray-100 rounded-lg items-center justify-center">
              <p className="text-sm text-gray-400">Preview unavailable</p>
            </div>
          </div>

          {/* Overall confidence score */}
          <div className="card p-4">
            <h2 className="section-heading">Overall Confidence</h2>
            <div className="flex items-center gap-4">
              {/* Circular indicator (uses SVG stroke-dasharray trick) */}
              <div className="relative w-16 h-16 flex-shrink-0">
                <svg className="w-16 h-16 -rotate-90" viewBox="0 0 64 64">
                  <circle cx="32" cy="32" r="26" fill="none" strokeWidth="6" className="stroke-gray-100" />
                  <circle
                    cx="32" cy="32" r="26" fill="none" strokeWidth="6"
                    strokeLinecap="round"
                    strokeDasharray={`${overallPct * 1.634} 163.4`}  /* circumference = 2π×26 ≈ 163.4 */
                    className={overallColors.bar.replace("bg-", "stroke-")}
                  />
                </svg>
                <span className={`absolute inset-0 flex items-center justify-center
                                  text-sm font-bold tabular-nums ${overallColors.text}`}>
                  {overallPct}%
                </span>
              </div>
              <div>
                <p className={`text-lg font-bold ${overallColors.text}`}>
                  {overallPct >= 80 ? "High confidence" : overallPct >= 55 ? "Moderate confidence" : "Low confidence"}
                </p>
                <p className="text-xs text-gray-500 mt-0.5">
                  Mean of {Object.values(confidence).filter((v) => v > 0).length} detected fields
                </p>
              </div>
            </div>
          </div>

          {/* Raw text collapsible */}
          <div className="card p-4">
            <RawTextPanel text={uploadResult.text} charCount={uploadResult.char_count} />
          </div>
        </div>

        {/* ── RIGHT COLUMN: Extracted Fields ────────────────────────────── */}
        <div className="lg:col-span-3 space-y-5">

          {/* Main fields */}
          <div className="card">
            <div className="flex items-center justify-between mb-2">
              <h2 className="section-heading mb-0">Extracted Fields</h2>
              <Badge className="bg-indigo-50 text-indigo-700 ring-indigo-200 text-xs">
                {extractionResult.document_type}
              </Badge>
            </div>

            <div className="divide-y divide-gray-100">
              {FIELD_NAMES.map((fieldName) => (
                <FieldCard
                  key={fieldName}
                  fieldName={fieldName}
                  value={fields[fieldName]}
                  confidence={confidence[fieldName] ?? 0}
                  source={null}    /* extraction_source not in current schema */
                  currency={fields.currency}
                />
              ))}
            </div>

            {/* Line items */}
            <LineItemsTable items={fields.line_items} currency={fields.currency} />
          </div>

          {/* Metadata card */}
          <div className="card p-4">
            <h2 className="section-heading">Processing Details</h2>
            <dl className="grid grid-cols-2 gap-3 text-sm">
              {[
                ["File type",    uploadResult.file_type?.toUpperCase() || "—"],
                ["Pages",        uploadResult.page_count],
                ["Text length",  `${uploadResult.char_count?.toLocaleString() || 0} chars`],
                ["Fields found", `${Object.values(confidence).filter((v) => v > 0).length} / ${FIELD_NAMES.length}`],
              ].map(([key, val]) => (
                <div key={key} className="bg-gray-50 rounded-lg px-3 py-2">
                  <dt className="text-xs text-gray-500 font-medium">{key}</dt>
                  <dd className="mt-0.5 font-semibold text-gray-900">{val}</dd>
                </div>
              ))}
            </dl>
          </div>

        </div>
      </div>
    </div>
  );
}
