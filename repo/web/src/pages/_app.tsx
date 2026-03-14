import React from "react";

import type { AppProps } from "next/app";

import "../styles/global.css";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand">KiloQuant</div>
        <nav className="app-nav">
          <a href="/" className="nav-link">首页</a>
          <a href="/insights" className="nav-link">数据洞察</a>
          <a href="/macro" className="nav-link">宏观指标</a>
          <a href="/stats" className="nav-link">统计面板</a>
        </nav>
      </header>
      <main className="app-main">
        <Component {...pageProps} />
      </main>
    </div>
  );
}
