import React from "react";

import type { AppProps } from "next/app";

import "../styles/global.css";

const NAV_LINKS = [
  { href: "/", label: "总览" },
  { href: "/stocks", label: "股票" },
  { href: "/insights", label: "洞察" },
  { href: "/macro", label: "宏观" },
  { href: "/stats", label: "统计" },
  { href: "/futures", label: "期货" },
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
