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
          <span className={styles.eyebrow}>实时监控</span>
          <span className={styles.route}>{route}</span>
        </div>
        <button
          type="button"
          className={styles.toggle}
          onClick={() => setCollapsed((value) => !value)}
        >
          {collapsed ? "展开" : "收起"}
        </button>
      </div>

      {!collapsed ? (
        <div className={styles.body}>
          <div className={styles.metrics}>
            <div className={styles.metric}>
              <div className={styles.metricLabel}>首字节时间</div>
              <div className={styles.metricValue}>
                {formatMs(snapshot.webVitals.TTFB?.valueMs)}
              </div>
              <div className={styles.metricHelper}>浏览器 Web 指标</div>
            </div>
            <div className={styles.metric}>
              <div className={styles.metricLabel}>首次内容绘制</div>
              <div className={styles.metricValue}>
                {formatMs(snapshot.webVitals.FCP?.valueMs)}
              </div>
              <div className={styles.metricHelper}>Browser web vital</div>
            </div>
            <div className={styles.metric}>
              <div className={styles.metricLabel}>API 平均耗时</div>
              <div className={styles.metricValue}>
                {formatMs(snapshot.averageRequestDurationMs)}
              </div>
              <div className={styles.metricHelper}>
                平均首字节时间 {formatMs(snapshot.averageRequestTtfbMs)}
              </div>
            </div>
            <div className={styles.metric}>
              <div className={styles.metricLabel}>缓存命中率</div>
              <div className={styles.metricValue}>
                {formatPercent(snapshot.queryCacheHitRate)}
              </div>
              <div className={styles.metricHelper}>
                后端 {formatPercent(snapshot.backendCacheHitRate)}
              </div>
            </div>
          </div>

          <section className={styles.section}>
            <div className={styles.sectionTitle}>最近请求</div>
            {snapshot.recentRequests.length ? (
              <div className={styles.list}>
                {snapshot.recentRequests.map((item) => (
                  <div key={`${item.recordedAt}-${item.url}`} className={styles.row}>
                    <div className={styles.rowMain}>
                      <span className={styles.rowLabel}>{item.label}</span>
                      <div className={styles.rowMeta}>
                        {item.status}
                        {typeof item.backendCacheHit === "boolean"
                          ? ` | 后端 ${item.backendCacheHit ? "命中" : "未命中"}`
                          : ""}
                      </div>
                    </div>
                    <div className={styles.rowValue}>
                      <span>{formatMs(item.durationMs)}</span>
                      <span>{`首字节时间 ${formatMs(item.ttfbMs)}`}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className={styles.empty}>此页面尚未捕获网络请求。</div>
            )}
          </section>

          <section className={styles.section}>
            <div className={styles.sectionTitle}>最近查询缓存</div>
            {snapshot.recentQueries.length ? (
              <div className={styles.list}>
                {snapshot.recentQueries.map((item) => (
                  <div key={`${item.recordedAt}-${item.label}`} className={styles.row}>
                    <div className={styles.rowMain}>
                      <span className={styles.rowLabel}>{item.label}</span>
                      <div className={styles.rowMeta}>{item.cacheSource}</div>
                    </div>
                    <div className={styles.rowValue}>
                      <span>{item.cacheHit ? "命中" : "未命中"}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className={styles.empty}>此页面尚未捕获查询缓存活动。</div>
            )}
          </section>
        </div>
      ) : null}
    </aside>
  );
}
