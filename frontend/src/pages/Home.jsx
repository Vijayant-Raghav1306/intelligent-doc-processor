/*
 * pages/Home.jsx — landing page / dashboard.
 *
 * Uses useEffect to ping the /health endpoint and display backend status.
 * useEffect runs once after the component mounts (empty [] dependency array).
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Upload, CheckCircle, XCircle, Loader, FileSearch,
         Cpu, Shield, Zap, FileText } from "lucide-react";
import { checkHealth } from "../services/api.js";

// Feature cards shown on the homepage
const FEATURES = [
  {
    Icon: Cpu,
    title: "Hybrid Extraction",
    desc: "Combines regex patterns with spaCy NLP for maximum accuracy. When both agree, confidence gets a boost.",
    color: "text-indigo-600",
    bg:   "bg-indigo-50",
  },
  {
    Icon: FileSearch,
    title: "Multi-Format OCR",
    desc: "Handles PDF (native + scanned), JPEG, PNG, TIFF, WebP, and DOCX. Tesseract OCR for image-based docs.",
    color: "text-emerald-600",
    bg:   "bg-emerald-50",
  },
  {
    Icon: Shield,
    title: "Confidence Scoring",
    desc: "Every extracted field gets a confidence score (0-100%). Visual bars show how reliable each value is.",
    color: "text-amber-600",
    bg:   "bg-amber-50",
  },
  {
    Icon: Zap,
    title: "Instant Results",
    desc: "Upload a document and get structured JSON back in seconds. Vendor, dates, amounts, line items — all extracted.",
    color: "text-purple-600",
    bg:   "bg-purple-50",
  },
];

// Supported document types
const DOC_TYPES = [
  { label: "Invoice",  emoji: "🧾" },
  { label: "Receipt",  emoji: "🪙" },
  { label: "PDF",      emoji: "📄" },
  { label: "Scanned",  emoji: "🖨️" },
  { label: "DOCX",     emoji: "📝" },
  { label: "Image",    emoji: "🖼️" },
];

export default function Home() {
  const navigate = useNavigate();
  const [healthStatus, setHealthStatus] = useState("checking"); // "checking" | "ok" | "error"
  const [healthData, setHealthData]     = useState(null);

  // Ping the backend health endpoint when the page loads
  useEffect(() => {
    checkHealth()
      .then((data) => {
        setHealthData(data);
        setHealthStatus("ok");
      })
      .catch(() => setHealthStatus("error"));
  }, []); // [] = run only once on mount, not on every re-render

  return (
    <div className="space-y-12">

      {/* ── Hero section ─────────────────────────────────────────────────── */}
      <section className="text-center pt-8">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-indigo-50 text-indigo-700
                        rounded-full text-xs font-semibold mb-6 ring-1 ring-indigo-200">
          <Cpu className="w-3.5 h-3.5" />
          AI-Powered Document Processing
        </div>

        <h1 className="text-4xl sm:text-5xl font-bold text-gray-900 leading-tight tracking-tight">
          Extract structured data<br />
          <span className="text-indigo-600">from any document</span>
        </h1>

        <p className="mt-5 text-lg text-gray-600 max-w-xl mx-auto leading-relaxed">
          Upload an invoice, receipt, or scanned document. Get back clean,
          structured JSON with vendor names, amounts, dates — and confidence scores.
        </p>

        <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-3">
          <button
            onClick={() => navigate("/upload")}
            className="btn-primary text-base px-7 py-3 rounded-xl shadow-md hover:shadow-lg"
          >
            <Upload className="w-5 h-5" />
            Process a Document
          </button>

          {/* Backend status indicator */}
          <div className="flex items-center gap-1.5 text-sm">
            {healthStatus === "checking" && (
              <><Loader className="w-4 h-4 text-gray-400 animate-spin" />
                <span className="text-gray-500">Connecting to backend...</span></>
            )}
            {healthStatus === "ok" && (
              <><CheckCircle className="w-4 h-4 text-emerald-500" />
                <span className="text-emerald-700 font-medium">
                  Backend online {healthData?.nlp_ready ? "· NLP ready" : ""}
                </span></>
            )}
            {healthStatus === "error" && (
              <><XCircle className="w-4 h-4 text-rose-500" />
                <span className="text-rose-700 font-medium">Backend offline</span></>
            )}
          </div>
        </div>

        {/* Supported types strip */}
        <div className="mt-8 flex flex-wrap justify-center gap-2">
          {DOC_TYPES.map(({ label, emoji }) => (
            <span key={label} className="px-3 py-1.5 bg-white ring-1 ring-gray-200
                                          rounded-lg text-sm text-gray-600 shadow-sm">
              {emoji} {label}
            </span>
          ))}
        </div>
      </section>

      {/* ── Feature cards ─────────────────────────────────────────────────── */}
      <section>
        <h2 className="text-xl font-bold text-gray-900 text-center mb-8">
          How it works
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          {FEATURES.map(({ Icon, title, desc, color, bg }) => (
            <div key={title} className="card hover:shadow-md transition-shadow">
              <div className={`w-10 h-10 ${bg} rounded-xl flex items-center justify-center mb-4`}>
                <Icon className={`w-5 h-5 ${color}`} />
              </div>
              <h3 className="font-semibold text-gray-900 mb-2">{title}</h3>
              <p className="text-sm text-gray-600 leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Extraction fields preview ─────────────────────────────────────── */}
      <section className="card">
        <h2 className="section-heading">Extracted Fields</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {[
            ["Vendor Name",     "Acme Corporation"],
            ["Invoice Number",  "INV-2024-0042"],
            ["Invoice Date",    "Jan 15, 2024"],
            ["Due Date",        "Feb 14, 2024"],
            ["Total Amount",    "$4,320.00"],
            ["Currency",        "USD"],
          ].map(([label, value]) => (
            <div key={label} className="bg-gray-50 rounded-lg px-4 py-3">
              <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">{label}</p>
              <p className="text-sm font-semibold text-gray-900 mt-0.5 truncate">{value}</p>
            </div>
          ))}
        </div>
        <div className="mt-6 pt-4 border-t border-gray-100 text-center">
          <button onClick={() => navigate("/upload")} className="btn-primary">
            <FileText className="w-4 h-4" />
            Try with your document
          </button>
        </div>
      </section>

    </div>
  );
}
