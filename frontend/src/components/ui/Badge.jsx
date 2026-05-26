/*
 * components/ui/Badge.jsx — small colored label chip.
 *
 * Used to show extraction source: "regex+nlp", "regex", "nlp", "none".
 * Also used for file type labels, confidence labels.
 *
 * Tailwind ring-1 creates a subtle border using box-shadow (not border)
 * which avoids layout shifts.
 */
export default function Badge({ children, className = "" }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ring-1 ${className}`}
    >
      {children}
    </span>
  );
}
