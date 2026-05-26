/*
 * utils/formatters.js — pure functions for formatting data for display.
 *
 * "Pure" means: given the same input, always return the same output.
 * No side effects, no API calls, no state.
 * These functions are easy to test and reuse anywhere.
 */

/**
 * Format a currency amount for display.
 * Examples:
 *   formatAmount(1234.56, "USD") → "$1,234.56"
 *   formatAmount(9876.00, "EUR") → "EUR 9,876.00"
 *   formatAmount(null, "USD")    → "—"
 */
export function formatAmount(amount, currency) {
  if (amount == null) return "—"; // em dash
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "USD",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
  } catch {
    // Fallback if currency code is not valid ISO 4217
    return `${currency || ""} ${amount.toFixed(2)}`.trim();
  }
}

/**
 * Format an ISO date string for display.
 * Examples:
 *   formatDate("2024-01-15") → "Jan 15, 2024"
 *   formatDate(null)         → "—"
 */
export function formatDate(isoString) {
  if (!isoString) return "—";
  try {
    const date = new Date(isoString + "T12:00:00Z"); // force UTC to avoid off-by-one
    return date.toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      timeZone: "UTC",
    });
  } catch {
    return isoString; // return as-is if parsing fails
  }
}

/**
 * Format a confidence score as a percentage string.
 * Examples:
 *   formatConfidence(0.856) → "85.6%"
 *   formatConfidence(0)     → "0%"
 */
export function formatConfidence(score) {
  if (score == null) return "0%";
  return `${Math.round(score * 100)}%`;
}

/**
 * Returns Tailwind color classes based on a confidence score.
 * Used for both the confidence bar fill color and text color.
 *
 * Thresholds (from backend comments in schemas.py):
 *   >= 0.85  strong labeled match
 *   >= 0.65  labeled but less specific
 *   >= 0.40  unlabeled heuristic
 *    0.0     not found
 */
export function confidenceColors(score) {
  if (score >= 0.80) return { bar: "bg-emerald-500", text: "text-emerald-700", badge: "bg-emerald-50 text-emerald-700 ring-emerald-200" };
  if (score >= 0.55) return { bar: "bg-amber-400",   text: "text-amber-700",   badge: "bg-amber-50 text-amber-700 ring-amber-200" };
  if (score >  0.0 ) return { bar: "bg-rose-400",    text: "text-rose-700",    badge: "bg-rose-50 text-rose-700 ring-rose-200" };
  // score === 0 → not found
  return { bar: "bg-gray-300", text: "text-gray-400", badge: "bg-gray-50 text-gray-500 ring-gray-200" };
}

/**
 * Human-readable label for each field name.
 */
export const FIELD_LABELS = {
  vendor_name:    "Vendor Name",
  invoice_number: "Invoice Number",
  invoice_date:   "Invoice Date",
  due_date:       "Due Date",
  total_amount:   "Total Amount",
  currency:       "Currency",
};

/**
 * Format a field value for display given its field name.
 */
export function formatFieldValue(fieldName, value, currency) {
  if (value == null || value === "") return null;
  if (fieldName === "total_amount") return formatAmount(value, currency);
  if (fieldName === "invoice_date" || fieldName === "due_date") return formatDate(value);
  return String(value);
}

/**
 * Format file size in human-readable form.
 * Examples:
 *   formatFileSize(1024)     → "1.0 KB"
 *   formatFileSize(1048576)  → "1.0 MB"
 */
export function formatFileSize(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1_048_576).toFixed(1)} MB`;
}

/**
 * Get a display name and icon class for a MIME type.
 */
export function fileTypeInfo(mimeType) {
  const types = {
    "application/pdf": { label: "PDF",  color: "text-red-600"    },
    "image/jpeg":      { label: "JPEG", color: "text-blue-600"   },
    "image/jpg":       { label: "JPEG", color: "text-blue-600"   },
    "image/png":       { label: "PNG",  color: "text-green-600"  },
    "image/tiff":      { label: "TIFF", color: "text-purple-600" },
    "image/webp":      { label: "WebP", color: "text-orange-600" },
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                       { label: "DOCX", color: "text-indigo-600" },
  };
  return types[mimeType] || { label: mimeType || "File", color: "text-gray-600" };
}
