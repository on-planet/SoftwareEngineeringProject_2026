import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/router";

import type { AppProps } from "next/app";

import "../styles/global.css";
import { getCurrentUser } from "../services/api";
import { AUTH_CHANGED_EVENT, clearAuthToken, getAuthToken } from "../utils/auth";

const NAV_LINKS = [
  { href: "/", label: "总览" },
  { href: "/stocks", label: "股票" },
  { href: "/insights", label: "洞察" },
  { href: "/macro", label: "宏观" },
  { href: "/futures", label: "期货" },
];

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter();
  const [authEmail, setAuthEmail] = useState<string | null>(null);

  useEffect(() => {
    let disposed = false;

    const syncAuthUser = async () => {
      const token = getAuthToken();
      if (!token) {
        if (!disposed) {
          setAuthEmail(null);
        }
        return;
      }
      try {
        const user: any = await getCurrentUser(token);
        const identity = String(user?.account || user?.email || "");
        if (!disposed) {
          setAuthEmail(identity || null);
        }
      } catch {
        clearAuthToken();
        if (!disposed) {
          setAuthEmail(null);
        }
      }
    };

    const handleAuthChanged = () => {
      void syncAuthUser();
    };
    const handleRouteChanged = () => {
      void syncAuthUser();
    };

    void syncAuthUser();
    window.addEventListener(AUTH_CHANGED_EVENT, handleAuthChanged);
    router.events.on("routeChangeComplete", handleRouteChanged);

    return () => {
      disposed = true;
      window.removeEventListener(AUTH_CHANGED_EVENT, handleAuthChanged);
      router.events.off("routeChangeComplete", handleRouteChanged);
    };
  }, [router.events]);

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
          {authEmail ? (
            <>
              <Link href="/stats" className="nav-link">
                账号
              </Link>
              <span className="nav-link" style={{ background: "rgba(15, 23, 42, 0.08)", color: "#0f172a" }}>
                {authEmail}
              </span>
              <button
                type="button"
                className="nav-link-button"
                onClick={() => {
                  clearAuthToken();
                  setAuthEmail(null);
                }}
              >
                退出
              </button>
            </>
          ) : (
            <Link href="/auth" className="nav-link">
              账号
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
