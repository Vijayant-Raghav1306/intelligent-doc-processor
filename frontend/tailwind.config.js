// tailwind.config.js
// Tells Tailwind which files to scan for class names.
// Only classes found in these files will be included in the final CSS bundle.
/** @type {import("tailwindcss").Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx,ts,tsx}",
  ],
  theme: {
    extend: {
      // Custom animation for the processing spinner
      animation: {
        "spin-slow": "spin 2s linear infinite",
        "pulse-fast": "pulse 1s cubic-bezier(0.4, 0, 0.6, 1) infinite",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "Menlo", "monospace"],
      },
    },
  },
  plugins: [
    // @tailwindcss/forms resets browser default form styles
    // so inputs, selects, and textareas look consistent
    require("@tailwindcss/forms"),
  ],
};
