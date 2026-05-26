/*
 * App.jsx — root component, defines all routes.
 *
 * React Router v6 uses <Routes> + <Route> to map URLs to page components.
 * Each <Route> renders a page component when the URL matches.
 *
 * Route structure:
 *   /           → Home (dashboard / landing)
 *   /upload     → Upload page (drag-and-drop file picker)
 *   /results    → Results page (extracted fields + preview)
 *   *           → redirect to / (catch-all for unknown URLs)
 */
import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/layout/Layout.jsx";
import Home from "./pages/Home.jsx";
import Upload from "./pages/Upload.jsx";
import Results from "./pages/Results.jsx";

export default function App() {
  return (
    <Routes>
      {/* All routes share the same Layout (header + main area) */}
      <Route element={<Layout />}>
        <Route path="/"        element={<Home />}    />
        <Route path="/upload"  element={<Upload />}  />
        <Route path="/results" element={<Results />} />
        {/* Catch-all: any unknown URL redirects to home */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
