import React from "react";
import Link from "next/link";

import type { AppProps } from "next/app";

import { AuthProvider, useAuth } from "../providers/AuthProvider";
import "../styles/global.css";
import { clearAuthToken } from "../utils/auth";

const NAV_LINKS = [
  { href: "/", label: "Overview" },
  { href: "/stocks", label: "Stocks" },
  { href: "/insights", label: "Insights" },
  { href: "/macro", label: "Macro" },
  { href: "/futures", label: "Futures" },
  { href: "/alerts", label: "Alerts" },
];

function AppShell({ Component, pageProps }: AppProps) {
  const { authEmail, isAuthenticated } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand">KiloQuant</div>
        <nav className="app-nav">
          {NAV_LINKS.map((item) => (
            <Link key={item.href} href={item.href} className="nav-link">
              {item.label}
            </Link>
          ))}
          {isAuthenticated ? (
            <>
              <Link href="/stats" className="nav-link">
                Workspace
              </Link>
              <span className="nav-link" style={{ background: "rgba(15, 23, 42, 0.08)", color: "#0f172a" }}>
                {authEmail}
              </span>
              <button
                type="button"
                className="nav-link-button"
                onClick={() => {
                  clearAuthToken();
                }}
              >
                Logout
              </button>
            </>
          ) : (
            <Link href="/auth" className="nav-link">
              Account
            </Link>
          )}
        </nav>
      </header>
      <main className="app-main">
        <Component {...pageProps} />
      </main>
    </div>
  );
}

export default function App(props: AppProps) {
  return (
    <AuthProvider>
      <AppShell {...props} />
    </AuthProvider>
  );
}
