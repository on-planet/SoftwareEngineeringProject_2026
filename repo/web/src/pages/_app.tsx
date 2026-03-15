import React from "react";

import type { AppProps } from "next/app";

import "../styles/global.css";

const NAV_LINKS = [
  { href: "/", label: "Home" },
  { href: "/stocks", label: "Stocks" },
  { href: "/insights", label: "Insights" },
  { href: "/macro", label: "Macro" },
  { href: "/stats", label: "Stats" },
  { href: "/futures", label: "Futures" },
];

export default function App({ Component, pageProps }: AppProps) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand">KiloQuant</div>
        <nav className="app-nav">
          {NAV_LINKS.map((item) => (
            <a key={item.href} href={item.href} className="nav-link">
              {item.label}
            </a>
          ))}
        </nav>
      </header>
      <main className="app-main">
        <Component {...pageProps} />
      </main>
    </div>
  );
}
