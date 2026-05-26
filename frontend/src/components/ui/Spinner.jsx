/*
 * components/ui/Spinner.jsx — reusable loading spinner.
 *
 * Takes an optional "size" prop: "sm" | "md" | "lg"
 * Uses Tailwind "animate-spin" — a CSS animation built into Tailwind.
 */
export default function Spinner({ size = "md", className = "" }) {
  const sizes = {
    sm: "w-4 h-4 border-2",
    md: "w-7 h-7 border-2",
    lg: "w-10 h-10 border-3",
  };
  return (
    <div
      className={`rounded-full border-gray-200 border-t-indigo-600 animate-spin ${sizes[size]} ${className}`}
      role="status"
      aria-label="Loading"
    />
  );
}
