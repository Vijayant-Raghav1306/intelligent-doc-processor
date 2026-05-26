/*
 * components/layout/Header.jsx — top navigation bar.
 *
 * Concepts used:
 *   - useLocation() from React Router: reads the current URL path
 *     so we can highlight the active navigation link.
 *   - NavLink: like <Link> but adds an "active" class automatically.
 */
import { NavLink, useLocation } from "react-router-dom";
import { FileSearch, Upload, Home } from "lucide-react";

const NAV_LINKS = [
  { to: "/",       label: "Home",    Icon: Home       },
  { to: "/upload", label: "Process", Icon: Upload     },
];

export default function Header() {
  return (
    <header className="bg-white border-b border-gray-200 sticky top-0 z-40 shadow-sm">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">

          {/* Logo / Brand */}
          <NavLink to="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center shadow-sm">
              <FileSearch className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-gray-900 text-base tracking-tight">
              DocProcessor
            </span>
          </NavLink>

          {/* Navigation */}
          <nav className="flex items-center gap-1">
            {NAV_LINKS.map(({ to, label, Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}    // "end" means only match exact "/" not "/upload"
                className={({ isActive }) =>
                  `flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-indigo-50 text-indigo-700"
                      : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                  }`
                }
              >
                <Icon className="w-4 h-4" />
                {label}
              </NavLink>
            ))}
          </nav>
        </div>
      </div>
    </header>
  );
}
