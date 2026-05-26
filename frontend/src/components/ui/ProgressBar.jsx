/*
 * components/ui/ProgressBar.jsx — animated progress bar.
 *
 * The bar width is controlled by the "value" prop (0-100).
 * CSS transition makes the fill animate smoothly as value changes.
 *
 * The style attribute is used here instead of Tailwind because the width
 * is a dynamic number — Tailwind classes are static strings known at
 * build time, so `w-[${value}%]` would not work in all setups.
 */
export default function ProgressBar({ value = 0, label = "", className = "" }) {
  return (
    <div className={className}>
      {label && (
        <div className="flex justify-between items-center mb-1.5">
          <span className="text-sm font-medium text-gray-700">{label}</span>
          <span className="text-sm font-mono text-gray-500">{Math.round(value)}%</span>
        </div>
      )}
      {/* Track */}
      <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
        {/* Fill */}
        <div
          className="h-2 rounded-full bg-indigo-600 transition-all duration-300 ease-out"
          style={{ width: `${Math.min(100, Math.max(0, value))}%` }}
          role="progressbar"
          aria-valuenow={value}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
    </div>
  );
}
