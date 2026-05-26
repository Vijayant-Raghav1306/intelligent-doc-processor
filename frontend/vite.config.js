// vite.config.js
// Vite is the build tool + dev server for React.
// It replaces Create React App and is much faster.
// Hot Module Replacement (HMR) means edits show in the browser instantly.
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],

  server: {
    port: 5173,   // local dev server port

    // Proxy: during local dev, any request to /api/* is forwarded
    // to your FastAPI backend. This avoids CORS issues in development.
    // In production (Vercel), you set VITE_API_URL instead.
    proxy: {
      "/documents": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/outputs": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/health": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
