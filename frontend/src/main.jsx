/*
 * main.jsx — the entry point for the React application.
 *
 * React 18 uses createRoot() instead of the old ReactDOM.render().
 * StrictMode runs every component twice in development to catch bugs early.
 * BrowserRouter enables React Router so we can have multiple pages (routes).
 */
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
