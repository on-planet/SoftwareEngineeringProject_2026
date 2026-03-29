import { useEffect, useState } from "react";

export type WebVitalName = "TTFB" | "FCP";
export type QueryCacheSource = "memory" | "persistent" | "stale" | "network";

export type WebVitalEntry = {
  route: string;
  name: WebVitalName;
  valueMs: number;
  recordedAt: number;
};

export type RequestMetricEntry = {
  route: string;
  label: string;
  url: string;
  status: number;
  durationMs: number;
  ttfbMs: number | null;
  backendCacheHit: boolean | null;
  recordedAt: number;
};

export type QueryMetricEntry = {
  route: string;
  label: string;
  cacheSource: QueryCacheSource;
  cacheHit: boolean;
  recordedAt: number;
};

export type PagePerformanceSnapshot = {
  route: string;
  webVitals: Partial<Record<WebVitalName, WebVitalEntry>>;
  averageRequestDurationMs: number | null;
  averageRequestTtfbMs: number | null;
  queryCacheHitRate: number | null;
  backendCacheHitRate: number | null;
  recentRequests: RequestMetricEntry[];
  recentQueries: QueryMetricEntry[];
};

const MAX_REQUEST_METRICS = 120;
const MAX_QUERY_METRICS = 180;
const MAX_RECENT_ITEMS = 6;

let activeRoute = "/";
const listeners = new Set<() => void>();
const webVitalsByRoute = new Map<string, Map<WebVitalName, WebVitalEntry>>();
const requestMetrics: RequestMetricEntry[] = [];
const queryMetrics: QueryMetricEntry[] = [];

function notifyListeners() {
  listeners.forEach((listener) => listener());
}

function pushBounded<T>(items: T[], value: T, maxSize: number) {
  items.push(value);
  if (items.length > maxSize) {
    items.splice(0, items.length - maxSize);
  }
}

function average(values: number[]) {
  if (!values.length) {
    return null;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function rate(hitCount: number, totalCount: number) {
  if (!totalCount) {
    return null;
  }
  return hitCount / totalCount;
}

export function sanitizePerformanceRoute(route?: string | null) {
  const fallback =
    typeof window !== "undefined" ? window.location.pathname || "/" : "/";
  const value = String(route || fallback).split("?")[0].split("#")[0].trim();
  return value || "/";
}

export function getActivePerformanceRoute() {
  return activeRoute;
}

export function setActivePerformanceRoute(route?: string | null) {
  const normalized = sanitizePerformanceRoute(route);
  if (normalized === activeRoute) {
    return;
  }
  activeRoute = normalized;
  notifyListeners();
}

export function recordWebVital(name: WebVitalName, valueMs: number, route?: string | null) {
  const normalizedRoute = sanitizePerformanceRoute(route);
  const entry: WebVitalEntry = {
    route: normalizedRoute,
    name,
    valueMs,
    recordedAt: Date.now(),
  };
  const byName = webVitalsByRoute.get(normalizedRoute) ?? new Map<WebVitalName, WebVitalEntry>();
  byName.set(name, entry);
  webVitalsByRoute.set(normalizedRoute, byName);
  notifyListeners();
}

export function recordRequestMetric(
  payload: Omit<RequestMetricEntry, "recordedAt"> & { route?: string | null },
) {
  const entry: RequestMetricEntry = {
    ...payload,
    route: sanitizePerformanceRoute(payload.route),
    recordedAt: Date.now(),
  };
  pushBounded(requestMetrics, entry, MAX_REQUEST_METRICS);
  notifyListeners();
}

export function recordQueryMetric(
  payload: Omit<QueryMetricEntry, "recordedAt"> & { route?: string | null },
) {
  const entry: QueryMetricEntry = {
    ...payload,
    route: sanitizePerformanceRoute(payload.route),
    recordedAt: Date.now(),
  };
  pushBounded(queryMetrics, entry, MAX_QUERY_METRICS);
  notifyListeners();
}

export function subscribePerformanceMetrics(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getPagePerformanceSnapshot(route?: string | null): PagePerformanceSnapshot {
  const normalizedRoute = sanitizePerformanceRoute(route);
  const pageWebVitals = webVitalsByRoute.get(normalizedRoute);
  const recentRequests = requestMetrics
    .filter((item) => item.route === normalizedRoute)
    .slice(-MAX_RECENT_ITEMS)
    .reverse();
  const recentQueries = queryMetrics
    .filter((item) => item.route === normalizedRoute)
    .slice(-MAX_RECENT_ITEMS)
    .reverse();
  const durationValues = recentRequests
    .map((item) => item.durationMs)
    .filter((item) => Number.isFinite(item));
  const ttfbValues = recentRequests
    .map((item) => item.ttfbMs)
    .filter((item): item is number => typeof item === "number" && Number.isFinite(item));
  const backendCacheSample = recentRequests.filter(
    (item) => typeof item.backendCacheHit === "boolean",
  );

  return {
    route: normalizedRoute,
    webVitals: {
      TTFB: pageWebVitals?.get("TTFB"),
      FCP: pageWebVitals?.get("FCP"),
    },
    averageRequestDurationMs: average(durationValues),
    averageRequestTtfbMs: average(ttfbValues),
    queryCacheHitRate: rate(
      recentQueries.filter((item) => item.cacheHit).length,
      recentQueries.length,
    ),
    backendCacheHitRate: rate(
      backendCacheSample.filter((item) => item.backendCacheHit).length,
      backendCacheSample.length,
    ),
    recentRequests,
    recentQueries,
  };
}

export function usePagePerformanceSnapshot(route?: string | null) {
  const normalizedRoute = sanitizePerformanceRoute(route);
  const [snapshot, setSnapshot] = useState<PagePerformanceSnapshot>(() =>
    getPagePerformanceSnapshot(normalizedRoute),
  );

  useEffect(() => {
    setSnapshot(getPagePerformanceSnapshot(normalizedRoute));
    return subscribePerformanceMetrics(() => {
      setSnapshot(getPagePerformanceSnapshot(normalizedRoute));
    });
  }, [normalizedRoute]);

  return snapshot;
}
