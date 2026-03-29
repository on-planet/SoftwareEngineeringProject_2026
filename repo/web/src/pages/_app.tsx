import React, { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/router";

import type { AppProps } from "next/app";

import { PerformanceMonitorPanel } from "../components/performance/PerformanceMonitorPanel";
import { AuthProvider, useAuth } from "../providers/AuthProvider";
import "../styles/global.css";
import { clearAuthToken } from "../utils/auth";
import { recordWebVital, setActivePerformanceRoute } from "../utils/performanceMonitor";

const NAV_LINKS = [
  { href: "/", label: "概览" },
  { href: "/stocks", label: "股票" },
  { href: "/strategy/smoke-butt", label: "策略" },
  { href: "/insights", label: "洞察" },
  { href: "/macro", label: "宏观" },
  { href: "/futures", label: "期货" },
  { href: "/alerts", label: "预警" },
];

function AppShell({ Component, pageProps }: AppProps) {
  const { authEmail, isAuthenticated, isAdmin, isAdminMode, setAdminMode } = useAuth();
  const router = useRouter();

  useEffect(() => {
    setActivePerformanceRoute(router.asPath);
  }, [router.asPath]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-brand">QuantPulse</div>
        <nav className="app-nav">
          {NAV_LINKS.map((item) => (
            <Link key={item.href} href={item.href} className="nav-link">
              {item.label}
            </Link>
          ))}
          {isAuthenticated ? (
            <>
              <Link href="/stats" className="nav-link">
                个人空间
              </Link>
              {isAdmin ? (
                <button
                  type="button"
                  className="nav-link-toggle"
                  data-active={isAdminMode}
                  onClick={() => setAdminMode(!isAdminMode)}
                >
                  {isAdminMode ? "退出管理员模式" : "进入管理员模式"}
                </button>
              ) : null}
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
                登出
              </button>
            </>
          ) : (
            <Link href="/auth" className="nav-link">
              账户
            </Link>
          )}
        </nav>
      </header>
      <main className="app-main">
        <Component {...pageProps} />
      </main>
      <PerformanceMonitorPanel />
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

export function reportWebVitals(metric: { name: string; value: number }) {
  if (metric.name === "TTFB" || metric.name === "FCP") {
    recordWebVital(metric.name, metric.value);
  }
}
