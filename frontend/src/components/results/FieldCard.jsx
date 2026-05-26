/*
 * components/results/FieldCard.jsx — displays a single extracted field.
 *
 * Shows:
 *   - Field label (e.g., "Vendor Name")
 *   - Extracted value (formatted) or "Not found" if null
 *   - Confidence bar with percentage and source tag
 */
import ConfidenceBar from "./ConfidenceBar.jsx";
import { formatFieldValue, FIELD_LABELS } from "../../utils/formatters.js";

export default function FieldCard({ fieldName, value, confidence, source, currency }) {
  const label = FIELD_LABELS[fieldName] || fieldName;
  const formattedValue = formatFieldValue(fieldName, value, currency);
  const isFound = formattedValue !== null;

  return (
    <div className="flex flex-col gap-2 py-4 border-b border-gray-100 last:border-0">
      {/* Header row: label + value */}
      <div className="flex items-start justify-between gap-4">
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide mt-0.5 flex-shrink-0">
          {label}
        </span>
        <span className={`text-sm font-semibold text-right ${
          isFound ? "text-gray-900" : "text-gray-400 italic"
        }`}>
          {isFound ? formattedValue : "Not found"}
        </span>
      </div>

      {/* Confidence bar */}
      <ConfidenceBar score={confidence} source={source} />
    </div>
  );
}
