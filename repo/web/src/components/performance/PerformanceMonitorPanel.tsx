import { useRouter } from "next/router";
import React, { useMemo, useState } from "react";

import { useAuth } from "../../providers/AuthProvider";
import {
  sanitizePerformanceRoute,
  usePagePerformanceSnapshot,
} from "../../utils/performanceMonitor";

import styles from "./PerformanceMonitorPanel.module.css";

function formatMs(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return `${value.toFixed(value >= 100 ? 0 : 1)} ms`;
}

function formatPercent(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "--";
  }
  return `${(value * 100).toFixed(0)}%`;
}

function shouldShowPerformancePanel(route: string) {
  return (
    route === "/" ||
    route.startsWith("/macro") ||
    route.startsWith("/stats") ||
    route.startsWith("/stocks") ||
    route.startsWith("/stock/")
  );
}

export function PerformanceMonitorPanel() {
  const { isAuthenticated, isAdminMode } = useAuth();
  const router = useRouter();
  const route = useMemo(
    () => sanitizePerformanceRoute(router.asPath),
    [router.asPath],
  );
  const snapshot = usePagePerformanceSnapshot(route);
  const [collapsed, setCollapsed] = useState(false);

  if (!isAuthenticated || !isAdminMode || !shouldShowPerformancePanel(route)) {
    return null;
  }

  return (
    <aside className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.title}>
          <span className={styles.eyebrow}>Real Monitor</span>
          <span className={styles.route}>{route}</span>
        </div>
        <button
          type="button"
          className={styles.toggle}
          onClick={() => setCollapsed((value) => !value)}
        >
          {collapsed ? "Expand" : "Collapse"}
        </button>
      </div>

      {!collapsed ? (
        <div className={styles.body}>
          <div className={styles.metrics}>
            <div className={styles.metric}>
              <div className={styles.metricLabel}>TTFB</div>
              <div className={styles.metricValue}>
                {formatMs(snapshot.webVitals.TTFB?.valueMs)}
              </div>
              <div className={styles.metricHelper}>Browser web vital</div>
            </div>
            <div className={styles.metric}>
              <div className={styles.metricLabel}>FCP</div>
              <div className={styles.metricValue}>
                {formatMs(snapshot.webVitals.FCP?.valueMs)}
              </div>
              <div className={styles.metricHelper}>Browser web vital</div>
            </div>
            <div className={styles.metric}>
              <div className={styles.metricLabel}>API Avg</div>
              <div className={styles.metricValue}>
                {formatMs(snapshot.averageRequestDurationMs)}
              </div>
              <div className={styles.metricHelper}>
                Avg TTFB {formatMs(snapshot.averageRequestTtfbMs)}
              </div>
            </div>
            <div className={styles.metric}>
              <div className={styles.metricLabel}>Cache Hit</div>
              <div className={styles.metricValue}>
                {formatPercent(snapshot.queryCacheHitRate)}
              </div>
              <div className={styles.metricHelper}>
                Backend {formatPercent(snapshot.backendCacheHitRate)}
              </div>
            </div>
          </div>

          <section className={styles.section}>
            <div className={styles.sectionTitle}>Recent Requests</div>
            {snapshot.recentRequests.length ? (
              <div className={styles.list}>
                {snapshot.recentRequests.map((item) => (
                  <div key={`${item.recordedAt}-${item.url}`} className={styles.row}>
                    <div className={styles.rowMain}>
                      <span className={styles.rowLabel}>{item.label}</span>
                      <div className={styles.rowMeta}>
                        {item.status}
                        {typeof item.backendCacheHit === "boolean"
                          ? ` | backend ${item.backendCacheHit ? "hit" : "miss"}`
                          : ""}
                      </div>
                    </div>
                    <div className={styles.rowValue}>
                      <span>{formatMs(item.durationMs)}</span>
                      <span>{`TTFB ${formatMs(item.ttfbMs)}`}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className={styles.empty}>No network requests captured on this page yet.</div>
            )}
          </section>

          <section className={styles.section}>
            <div className={styles.sectionTitle}>Recent Query Cache</div>
            {snapshot.recentQueries.length ? (
              <div className={styles.list}>
                {snapshot.recentQueries.map((item) => (
                  <div key={`${item.recordedAt}-${item.label}`} className={styles.row}>
                    <div className={styles.rowMain}>
                      <span className={styles.rowLabel}>{item.label}</span>
                      <div className={styles.rowMeta}>{item.cacheSource}</div>
                    </div>
                    <div className={styles.rowValue}>
                      <span>{item.cacheHit ? "hit" : "miss"}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className={styles.empty}>No query cache activity captured on this page yet.</div>
            )}
          </section>
        </div>
      ) : null}
    </aside>
  );
}
