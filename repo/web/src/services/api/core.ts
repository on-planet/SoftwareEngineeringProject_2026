import {
  getPersistentCacheEntry,
  removePersistentCache,
  writePersistentCache,
} from "../../utils/persistentCache";
import {
  QueryCacheSource,
  getActivePerformanceRoute,
  recordQueryMetric,
  recordRequestMetric,
} from "../../utils/performanceMonitor";

const DEFAULT_STALE_TIME_MS = 5_000;
const DEFAULT_CACHE_TIME_MS = 60_000;
const DEFAULT_RETRY_COUNT = 1;
const DEFAULT_RETRY_DELAY_MS = 300;

export type ApiQueryPersistOptions = {
  key?: string;
  maxAgeMs: number;
};

export type ApiQueryOptions = {
  staleTimeMs?: number;
  cacheTimeMs?: number;
  retry?: number;
  retryDelayMs?: number;
  backgroundRefresh?: boolean;
  cache?: boolean;
  force?: boolean;
  persist?: ApiQueryPersistOptions;
  label?: string;
};

export type ApiQuerySnapshot<T> = {
  data: T | undefined;
  error: Error | null;
  isLoading: boolean;
  isFetching: boolean;
  updatedAt: number | null;
};

export type ApiPage<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  cache_hit?: boolean | null;
  as_of?: string | null;
  refresh_queued?: boolean | null;
  [key: string]: unknown;
};

type ApiQueryEntry = {
  data: unknown;
  error: Error | null;
  updatedAt: number | null;
  staleAt: number;
  expiresAt: number;
  inflight: Promise<unknown> | null;
  isFetching: boolean;
  listeners: Set<() => void>;
  gcTimer: ReturnType<typeof setTimeout> | null;
  persistKey: string | null;
};

const queryCache = new Map<string, ApiQueryEntry>();

function resolveRequestUrl(url: string) {
  if (typeof window === "undefined") {
    return url;
  }
  try {
    return new URL(url, window.location.origin).toString();
  } catch {
    return url;
  }
}

function resolveRequestTimings(url: string, startedAt: number, finishedAt: number) {
  if (typeof performance === "undefined" || typeof PerformanceResourceTiming === "undefined") {
    return {
      durationMs: Math.max(finishedAt - startedAt, 0),
      ttfbMs: null,
    };
  }

  const requestUrl = resolveRequestUrl(url);
  const entries = performance
    .getEntriesByName(requestUrl)
    .filter(
      (entry): entry is PerformanceResourceTiming =>
        entry instanceof PerformanceResourceTiming &&
        entry.initiatorType === "fetch" &&
        entry.startTime >= startedAt - 1,
    );
  const entry = entries[entries.length - 1];
  if (!entry) {
    return {
      durationMs: Math.max(finishedAt - startedAt, 0),
      ttfbMs: null,
    };
  }
  return {
    durationMs:
      entry.responseEnd > entry.startTime
        ? entry.responseEnd - entry.startTime
        : Math.max(finishedAt - startedAt, 0),
    ttfbMs:
      entry.responseStart > entry.startTime
        ? entry.responseStart - entry.startTime
        : null,
  };
}

function extractBackendCacheHit(payload: unknown) {
  if (!payload || typeof payload !== "object") {
    return null;
  }
  const value = (payload as { cache_hit?: unknown }).cache_hit;
  return typeof value === "boolean" ? value : null;
}

async function requestWithInit<T = any>(url: string, init?: RequestInit, label?: string): Promise<T> {
  const route = getActivePerformanceRoute();
  const startedAt = typeof performance !== "undefined" ? performance.now() : Date.now();
  const requestUrl = resolveRequestUrl(url);
  const res = await fetch(url, init);
  const finishedAt = typeof performance !== "undefined" ? performance.now() : Date.now();
  const timing = resolveRequestTimings(requestUrl, startedAt, finishedAt);
  if (!res.ok) {
    const text = await res.text();
    recordRequestMetric({
      route,
      label: label || url,
      url: requestUrl,
      status: res.status,
      durationMs: timing.durationMs,
      ttfbMs: timing.ttfbMs,
      backendCacheHit: null,
    });
    throw new Error(text || `Request failed: ${res.status}`);
  }
  const payload = (await res.json()) as T;
  recordRequestMetric({
    route,
    label: label || url,
    url: requestUrl,
    status: res.status,
    durationMs: timing.durationMs,
    ttfbMs: timing.ttfbMs,
    backendCacheHit: extractBackendCacheHit(payload),
  });
  return payload;
}

function normalizeError(error: unknown) {
  return error instanceof Error ? error : new Error(String(error));
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => {
    setTimeout(resolve, ms);
  });
}

function buildRequestCacheKey(method: string, url: string) {
  return `${method.toUpperCase()}:${url}`;
}

function resolveQueryOptions(options?: ApiQueryOptions) {
  const staleTimeMs = options?.staleTimeMs ?? DEFAULT_STALE_TIME_MS;
  const cacheTimeMs = Math.max(options?.cacheTimeMs ?? DEFAULT_CACHE_TIME_MS, staleTimeMs);
  return {
    staleTimeMs,
    cacheTimeMs,
    retry: options?.retry ?? DEFAULT_RETRY_COUNT,
    retryDelayMs: options?.retryDelayMs ?? DEFAULT_RETRY_DELAY_MS,
    backgroundRefresh: options?.backgroundRefresh ?? true,
    cache: options?.cache ?? true,
    force: options?.force ?? false,
    label: options?.label ?? null,
    persist: options?.persist && options.persist.maxAgeMs > 0
      ? {
          key: options.persist.key,
          maxAgeMs: Math.max(1, options.persist.maxAgeMs),
        }
      : null,
  };
}

function getOrCreateQueryEntry(cacheKey: string): ApiQueryEntry {
  const existing = queryCache.get(cacheKey);
  if (existing) {
    return existing;
  }
  const entry: ApiQueryEntry = {
    data: undefined,
    error: null,
    updatedAt: null,
    staleAt: 0,
    expiresAt: 0,
    inflight: null,
    isFetching: false,
    listeners: new Set(),
    gcTimer: null,
    persistKey: null,
  };
  queryCache.set(cacheKey, entry);
  return entry;
}

function notifyQueryListeners(entry: ApiQueryEntry) {
  entry.listeners.forEach((listener) => listener());
}

function scheduleQueryGc(cacheKey: string, entry: ApiQueryEntry) {
  if (entry.gcTimer) {
    clearTimeout(entry.gcTimer);
    entry.gcTimer = null;
  }
  const delay = Math.max(entry.expiresAt - Date.now(), 0);
  entry.gcTimer = setTimeout(() => {
    const current = queryCache.get(cacheKey);
    if (!current || current !== entry) {
      return;
    }
    if (current.listeners.size > 0 || current.inflight) {
      scheduleQueryGc(cacheKey, current);
      return;
    }
    if (Date.now() >= current.expiresAt) {
      queryCache.delete(cacheKey);
    }
  }, delay + 1);
}

async function requestWithRetry<T>(execute: () => Promise<T>, options?: ApiQueryOptions): Promise<T> {
  const resolved = resolveQueryOptions(options);
  let attempt = 0;
  while (true) {
    try {
      return await execute();
    } catch (error) {
      const nextError = normalizeError(error);
      if (attempt >= resolved.retry) {
        throw nextError;
      }
      await sleep(resolved.retryDelayMs * (2 ** attempt));
      attempt += 1;
    }
  }
}

function hydrateQueryEntryFromPersistence<T>(cacheKey: string, entry: ApiQueryEntry, options?: ApiQueryOptions) {
  const resolved = resolveQueryOptions(options);
  if (!resolved.persist) {
    return false;
  }

  const persistKey = resolved.persist.key ?? cacheKey;
  entry.persistKey = persistKey;
  const persisted = getPersistentCacheEntry<T>(persistKey, resolved.persist.maxAgeMs);
  if (!persisted) {
    return false;
  }
  if (typeof entry.updatedAt === "number" && entry.updatedAt >= persisted.savedAt) {
    return false;
  }

  entry.data = persisted.value;
  entry.error = null;
  entry.updatedAt = persisted.savedAt;
  entry.staleAt = persisted.savedAt + resolved.staleTimeMs;
  entry.expiresAt = Date.now() + resolved.cacheTimeMs;
  entry.inflight = null;
  entry.isFetching = false;
  scheduleQueryGc(cacheKey, entry);
  return true;
}

function updateQuerySuccess<T>(cacheKey: string, entry: ApiQueryEntry, data: T, options?: ApiQueryOptions) {
  const resolved = resolveQueryOptions(options);
  const now = Date.now();
  entry.data = data;
  entry.error = null;
  entry.updatedAt = now;
  entry.staleAt = now + resolved.staleTimeMs;
  entry.expiresAt = now + resolved.cacheTimeMs;
  entry.isFetching = false;
  entry.inflight = null;
  if (resolved.persist) {
    entry.persistKey = resolved.persist.key ?? cacheKey;
    writePersistentCache(entry.persistKey, data);
  }
  notifyQueryListeners(entry);
  scheduleQueryGc(cacheKey, entry);
}

function updateQueryError(cacheKey: string, entry: ApiQueryEntry, error: unknown, options?: ApiQueryOptions) {
  const resolved = resolveQueryOptions(options);
  const nextError = normalizeError(error);
  entry.error = entry.data === undefined ? nextError : null;
  entry.staleAt = Math.max(entry.staleAt, Date.now() + resolved.retryDelayMs);
  entry.expiresAt = Math.max(entry.expiresAt, Date.now() + resolved.cacheTimeMs);
  entry.isFetching = false;
  entry.inflight = null;
  notifyQueryListeners(entry);
  scheduleQueryGc(cacheKey, entry);
}

function startQueryFetch<T>(cacheKey: string, fetcher: () => Promise<T>, options?: ApiQueryOptions): Promise<T> {
  const entry = getOrCreateQueryEntry(cacheKey);
  if (entry.inflight) {
    return entry.inflight as Promise<T>;
  }
  entry.isFetching = true;
  entry.error = null;
  notifyQueryListeners(entry);
  const inflight = requestWithRetry(fetcher, options)
    .then((data) => {
      updateQuerySuccess(cacheKey, entry, data, options);
      return data;
    })
    .catch((error) => {
      updateQueryError(cacheKey, entry, error, options);
      throw normalizeError(error);
    });
  entry.inflight = inflight;
  return inflight;
}

export function getApiQuerySnapshot<T>(
  cacheKey: string,
  options?: ApiQueryOptions,
  config?: { hydrateFromPersistence?: boolean },
): ApiQuerySnapshot<T> {
  const existing = queryCache.get(cacheKey);
  const shouldHydrateFromPersistence = config?.hydrateFromPersistence ?? true;
  const entry =
    options?.persist && shouldHydrateFromPersistence ? (existing ?? getOrCreateQueryEntry(cacheKey)) : existing;
  if (entry && options?.persist && shouldHydrateFromPersistence) {
    hydrateQueryEntryFromPersistence<T>(cacheKey, entry, options);
  }
  if (!entry) {
    return {
      data: undefined,
      error: null,
      isLoading: true,
      isFetching: false,
      updatedAt: null,
    };
  }
  return {
    data: entry.data as T | undefined,
    error: entry.error,
    isLoading: entry.data === undefined && entry.error === null && (entry.isFetching || entry.updatedAt === null),
    isFetching: entry.isFetching,
    updatedAt: entry.updatedAt,
  };
}

function recordCacheAccess(
  cacheKey: string,
  source: QueryCacheSource,
  cacheHit: boolean,
  options?: ApiQueryOptions,
) {
  recordQueryMetric({
    route: getActivePerformanceRoute(),
    label: options?.label || cacheKey,
    cacheSource: source,
    cacheHit,
  });
}

export function subscribeApiQuery(cacheKey: string, listener: () => void) {
  const entry = getOrCreateQueryEntry(cacheKey);
  entry.listeners.add(listener);
  return () => {
    entry.listeners.delete(listener);
    if (entry.listeners.size === 0) {
      scheduleQueryGc(cacheKey, entry);
    }
  };
}

export function invalidateApiQueries(matcher?: string | RegExp | ((cacheKey: string) => boolean)) {
  const matches = (cacheKey: string) => {
    if (!matcher) {
      return true;
    }
    if (typeof matcher === "string") {
      return cacheKey === matcher || cacheKey.startsWith(matcher);
    }
    if (matcher instanceof RegExp) {
      return matcher.test(cacheKey);
    }
    return matcher(cacheKey);
  };

  Array.from(queryCache.entries()).forEach(([cacheKey, entry]) => {
    if (!matches(cacheKey)) {
      return;
    }
    queryCache.delete(cacheKey);
    if (entry.persistKey) {
      removePersistentCache(entry.persistKey);
    }
    if (entry.gcTimer) {
      clearTimeout(entry.gcTimer);
    }
    entry.inflight = null;
    entry.isFetching = false;
    notifyQueryListeners(entry);
  });
}

export function runApiQuery<T>(cacheKey: string, fetcher: () => Promise<T>, options?: ApiQueryOptions): Promise<T> {
  const resolved = resolveQueryOptions(options);
  if (!resolved.cache) {
    recordCacheAccess(cacheKey, "network", false, options);
    return requestWithRetry(fetcher, options);
  }

  const entry = getOrCreateQueryEntry(cacheKey);
  const hydratedFromPersistence = resolved.persist
    ? hydrateQueryEntryFromPersistence<T>(cacheKey, entry, options)
    : false;
  const now = Date.now();
  const hasData = entry.data !== undefined;
  const isFresh = hasData && now < entry.staleAt;
  const isExpired = !hasData || now >= entry.expiresAt;

  if (resolved.force) {
    recordCacheAccess(cacheKey, "network", false, options);
    return startQueryFetch(cacheKey, fetcher, options);
  }
  if (isFresh) {
    recordCacheAccess(cacheKey, hydratedFromPersistence ? "persistent" : "memory", true, options);
    return Promise.resolve(entry.data as T);
  }
  if (hasData && !isExpired) {
    recordCacheAccess(cacheKey, hydratedFromPersistence ? "persistent" : "stale", true, options);
    if (resolved.backgroundRefresh && !entry.inflight) {
      void startQueryFetch(cacheKey, fetcher, options).catch(() => undefined);
    }
    return Promise.resolve(entry.data as T);
  }
  recordCacheAccess(cacheKey, "network", false, options);
  return startQueryFetch(cacheKey, fetcher, options);
}

export async function request<T = any>(url: string, options?: ApiQueryOptions): Promise<T> {
  const cacheKey = buildRequestCacheKey("GET", url);
  return runApiQuery<T>(cacheKey, () => requestWithInit<T>(url, undefined, options?.label), options);
}

export async function requestJson<T = any>(
  url: string,
  payload: Record<string, unknown>,
  options?: {
    method?: "POST" | "PUT" | "PATCH";
    token?: string;
    retry?: number;
    retryDelayMs?: number;
    label?: string;
  },
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (options?.token) {
    headers.Authorization = `Bearer ${options.token}`;
  }
  return requestWithRetry(
    () =>
      requestWithInit<T>(url, {
        method: options?.method ?? "POST",
        headers,
        body: JSON.stringify(payload),
      }, options?.label),
    { retry: options?.retry ?? 0, retryDelayMs: options?.retryDelayMs, cache: false },
  );
}

export async function requestAuthed<T = any>(
  url: string,
  token: string,
  options?: { retry?: number; retryDelayMs?: number; label?: string },
): Promise<T> {
  return requestWithRetry(
    () =>
      requestWithInit<T>(url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }, options?.label),
    { cache: false, retry: options?.retry, retryDelayMs: options?.retryDelayMs },
  );
}

export async function requestAuthedJson<T = any>(
  url: string,
  payload: Record<string, unknown>,
  token: string,
  options?: { method?: "POST" | "PUT" | "PATCH"; label?: string },
): Promise<T> {
  return requestJson<T>(url, payload, { token, method: options?.method, label: options?.label });
}

export async function requestAuthedDelete<T = any>(
  url: string,
  token: string,
  options?: { label?: string },
): Promise<T> {
  return requestWithRetry(
    () =>
      requestWithInit<T>(url, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }, options?.label),
    { retry: 0, cache: false },
  );
}

export function primeApiQuery<T>(cacheKey: string, data: T, options?: ApiQueryOptions) {
  const entry = getOrCreateQueryEntry(cacheKey);
  updateQuerySuccess(cacheKey, entry, data, options);
}
