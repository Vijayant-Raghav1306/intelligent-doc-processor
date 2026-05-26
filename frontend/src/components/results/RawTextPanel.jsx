/*
 * components/results/RawTextPanel.jsx — collapsible raw OCR text display.
 *
 * Uses the HTML <details>/<summary> elements — built-in collapse/expand
 * with no JavaScript needed. The browser handles the open/close toggle.
 * We add Tailwind classes to style it nicely.
 *
 * The raw text is displayed in a monospace font (JetBrains Mono) inside
 * a scrollable container with a max height.
 */
import { FileText } from "lucide-react";

export default function RawTextPanel({ text = "", charCount = 0 }) {
  if (!text) return null;

  return (
    <details className="group">
      <summary className="flex items-center justify-between cursor-pointer
                          py-3 px-4 bg-gray-50 rounded-lg ring-1 ring-gray-200
                          hover:bg-gray-100 transition-colors list-none">
        <div className="flex items-center gap-2">
          <FileText className="w-4 h-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-700">Raw Extracted Text</span>
          <span className="text-xs text-gray-400">{charCount.toLocaleString()} chars</span>
        </div>
        {/* Chevron rotates when open */}
        <svg
          className="w-4 h-4 text-gray-400 transition-transform duration-200 group-open:rotate-180"
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </summary>

      {/* Content shown when <details> is open */}
      <div className="mt-2 rounded-lg ring-1 ring-gray-200 overflow-hidden">
        <pre
          className="font-mono text-xs text-gray-700 bg-gray-50 p-4
                     overflow-auto max-h-64 scrollbar-thin leading-relaxed
                     whitespace-pre-wrap break-words"
        >
          {text}
        </pre>
      </div>
    </details>
  );
}
