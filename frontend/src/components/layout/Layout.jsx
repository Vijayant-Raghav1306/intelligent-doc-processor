/*
 * components/layout/Layout.jsx — the shared shell for every page.
 *
 * In React Router v6, a "layout route" wraps child routes.
 * <Outlet /> is where the current page renders.
 *
 * Structure:
 *   <Header />          ← fixed top bar
 *   <main>
 *     <Outlet />        ← Home / Upload / Results renders here
 *   </main>
 */
import { Outlet } from "react-router-dom";
import Header from "./Header.jsx";

export default function Layout() {
  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <Header />
      <main className="flex-1 w-full max-w-6xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <Outlet />
      </main>
      <footer className="py-6 text-center text-xs text-gray-400">
        Intelligent Document Processor &mdash; AI-powered extraction
      </footer>
    </div>
  );
}
