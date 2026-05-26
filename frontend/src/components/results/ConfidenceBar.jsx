/*
 * components/results/ConfidenceBar.jsx — visual confidence indicator.
 *
 * Shows:
 *   - A filled bar (green/amber/red based on score)
 *   - The percentage number
 *   - An optional source tag badge ("regex+nlp", "regex", "nlp", "none")
 */
import { confidenceColors, formatConfidence } from "../../utils/formatters.js";
import Badge from "../ui/Badge.jsx";

// Maps extraction source strings from the backend to display labels
const SOURCE_LABELS = {
  "regex+nlp": { label: "regex + nlp", title: "Both regex and NLP agreed on this value" },
  "regex":     { label: "regex",       title: "Extracted by regular expression pattern" },
  "nlp":       { label: "nlp",         title: "Extracted by spaCy NLP entity recognition" },
  "none":      { label: "not found",   title: "Field was not found in the document" },
};

const SOURCE_COLORS = {
  "regex+nlp": "bg-indigo-50 text-indigo-700 ring-indigo-200",
  "regex":     "bg-blue-50   text-blue-700   ring-blue-200",
  "nlp":       "bg-purple-50 text-purple-700 ring-purple-200",
  "none":      "bg-gray-50   text-gray-500   ring-gray-200",
};

export default function ConfidenceBar({ score = 0, source }) {
  const colors = confidenceColors(score);
  const pct    = Math.round(score * 100);
  const src    = SOURCE_LABELS[source];
  const srcClr = SOURCE_COLORS[source] || SOURCE_COLORS["none"];

  return (
    <div className="space-y-1.5">
      {/* Bar + percentage */}
      <div className="flex items-center gap-3">
        <div className="flex-1 bg-gray-100 rounded-full h-1.5 overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${colors.bar}`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className={`text-xs font-mono font-medium w-9 text-right tabular-nums ${colors.text}`}>
          {pct}%
        </span>
        {/* Source tag */}
        {src && (
          <Badge className={srcClr} title={src.title}>
            {src.label}
          </Badge>
        )}
      </div>
    </div>
  );
}
