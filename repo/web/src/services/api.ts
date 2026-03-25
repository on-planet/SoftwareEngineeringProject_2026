import {
  getPersistentCacheEntry,
  removePersistentCache,
  writePersistentCache,
} from "../utils/persistentCache";

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

export type KlinePoint = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

export type KlineSeriesResponse = {
  symbol: string;
  period: string;
  items: KlinePoint[];
};

export type CompareKlineSeriesRequest = {
  symbol: string;
  kind?: "stock" | "index";
  start?: string;
  end?: string;
};

export type CompareKlineSeriesResponse = {
  symbol: string;
  kind: "stock" | "index";
  period: string;
  items: KlinePoint[];
  error?: string | null;
};

export type CompareKlineResponse = {
  period: string;
  limit: number;
  series: CompareKlineSeriesResponse[];
};

async function requestWithInit<T = any>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
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
    return;
  }

  const persistKey = resolved.persist.key ?? cacheKey;
  entry.persistKey = persistKey;
  const persisted = getPersistentCacheEntry<T>(persistKey, resolved.persist.maxAgeMs);
  if (!persisted) {
    return;
  }
  if (typeof entry.updatedAt === "number" && entry.updatedAt >= persisted.savedAt) {
    return;
  }

  entry.data = persisted.value;
  entry.error = null;
  entry.updatedAt = persisted.savedAt;
  entry.staleAt = persisted.savedAt + resolved.staleTimeMs;
  entry.expiresAt = Date.now() + resolved.cacheTimeMs;
  entry.inflight = null;
  entry.isFetching = false;
  scheduleQueryGc(cacheKey, entry);
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

export function getApiQuerySnapshot<T>(cacheKey: string, options?: ApiQueryOptions): ApiQuerySnapshot<T> {
  const existing = queryCache.get(cacheKey);
  const entry = options?.persist ? (existing ?? getOrCreateQueryEntry(cacheKey)) : existing;
  if (entry && options?.persist) {
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
    return requestWithRetry(fetcher, options);
  }

  const entry = getOrCreateQueryEntry(cacheKey);
  if (resolved.persist) {
    hydrateQueryEntryFromPersistence<T>(cacheKey, entry, options);
  }
  const now = Date.now();
  const hasData = entry.data !== undefined;
  const isFresh = hasData && now < entry.staleAt;
  const isExpired = !hasData || now >= entry.expiresAt;

  if (resolved.force) {
    return startQueryFetch(cacheKey, fetcher, options);
  }
  if (isFresh) {
    return Promise.resolve(entry.data as T);
  }
  if (hasData && !isExpired) {
    if (resolved.backgroundRefresh && !entry.inflight) {
      void startQueryFetch(cacheKey, fetcher, options).catch(() => undefined);
    }
    return Promise.resolve(entry.data as T);
  }
  return startQueryFetch(cacheKey, fetcher, options);
}

async function request<T = any>(url: string, options?: ApiQueryOptions): Promise<T> {
  const cacheKey = buildRequestCacheKey("GET", url);
  return runApiQuery<T>(cacheKey, () => requestWithInit<T>(url), options);
}

async function requestJson<T = any>(
  url: string,
  payload: Record<string, unknown>,
  options?: { method?: "POST" | "PUT" | "PATCH"; token?: string; retry?: number; retryDelayMs?: number },
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
      }),
    { retry: options?.retry ?? 0, retryDelayMs: options?.retryDelayMs, cache: false },
  );
}

async function requestAuthed<T = any>(url: string, token: string): Promise<T> {
  return requestWithRetry(
    () =>
      requestWithInit<T>(url, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }),
    { cache: false },
  );
}

async function requestAuthedJson<T = any>(
  url: string,
  payload: Record<string, unknown>,
  token: string,
  options?: { method?: "POST" | "PUT" | "PATCH" },
): Promise<T> {
  return requestJson<T>(url, payload, { token, method: options?.method });
}

async function requestAuthedDelete<T = any>(url: string, token: string): Promise<T> {
  return requestWithRetry(
    () =>
      requestWithInit<T>(url, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      }),
    { retry: 0, cache: false },
  );
}

export async function getIndices(params?: { as_of?: string; sort?: "asc" | "desc"; limit?: number; offset?: number }) {
  const query = new URLSearchParams();
  if (params?.as_of) query.set("as_of", params.as_of);
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request(`/api/index${suffix ? `?${suffix}` : ""}`);
}

export async function getStocks(params?: {
  market?: "A" | "HK" | "US";
  keyword?: string;
  sector?: string;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.market) query.set("market", params.market);
  if (params?.keyword) query.set("keyword", params.keyword);
  if (params?.sector) query.set("sector", params.sector);
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request(`/api/stocks${suffix ? `?${suffix}` : ""}`);
}

export async function getIndexKline(symbol: string, params?: {
  period?: "1m" | "30m" | "60m" | "day" | "week" | "month" | "quarter" | "year";
  limit?: number;
  start?: string;
  end?: string;
}) {
  const query = new URLSearchParams();
  if (params?.period) query.set("period", params.period);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  const suffix = query.toString();
  return request<KlineSeriesResponse>(`/api/index/${encodeURIComponent(symbol)}/kline${suffix ? `?${suffix}` : ""}`);
}

export async function getStockKline(symbol: string, params?: {
  period?: "1m" | "30m" | "60m" | "day" | "week" | "month" | "quarter" | "year";
  limit?: number;
  start?: string;
  end?: string;
}) {
  const query = new URLSearchParams();
  if (params?.period) query.set("period", params.period);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  const suffix = query.toString();
  return request<KlineSeriesResponse>(`/api/stock/${encodeURIComponent(symbol)}/kline${suffix ? `?${suffix}` : ""}`);
}

export async function getCompareKline(payload: {
  period?: "1m" | "30m" | "60m" | "day" | "week" | "month" | "quarter" | "year";
  limit?: number;
  series: CompareKlineSeriesRequest[];
}) {
  return requestJson<CompareKlineResponse>(
    "/api/kline/compare",
    {
      period: payload.period ?? "day",
      limit: payload.limit ?? 200,
      series: payload.series,
    },
    { retry: 1 },
  );
}

export async function getFutures(params?: {
  symbol?: string;
  start?: string;
  end?: string;
  as_of?: string;
  frequency?: "day" | "week";
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.symbol) query.set("symbol", params.symbol);
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  if (params?.as_of) query.set("as_of", params.as_of);
  if (params?.frequency) query.set("frequency", params.frequency);
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request(`/api/futures${suffix ? `?${suffix}` : ""}`);
}

export async function getFuturesSeries(
  symbol: string,
  params?: { start?: string; end?: string; frequency?: "day" | "week" }
) {
  const query = new URLSearchParams();
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  if (params?.frequency) query.set("frequency", params.frequency);
  const suffix = query.toString();
  return request(`/api/futures/${encodeURIComponent(symbol)}/series${suffix ? `?${suffix}` : ""}`);
}

export async function getRisk(symbol: string) {
  return request(`/api/risk/${symbol}`);
}

export async function getRiskSeries(symbol: string, params?: {
  window?: number;
  limit?: number;
  start?: string;
  end?: string;
}) {
  const query = new URLSearchParams();
  if (params?.window !== undefined) query.set("window", String(params.window));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  const suffix = query.toString();
  return request(`/api/risk/${symbol}/series${suffix ? `?${suffix}` : ""}`);
}

export async function getIndicators(symbol: string, params?: {
  indicator?:
    | "ma"
    | "sma"
    | "ema"
    | "wma"
    | "rsi"
    | "macd"
    | "boll"
    | "kdj"
    | "atr"
    | "cci"
    | "wr"
    | "obv"
    | "roc"
    | "mom"
    | "adx"
    | "mfi";
  window?: number;
  limit?: number;
  start?: string;
  end?: string;
}) {
  const query = new URLSearchParams();
  if (params?.indicator) query.set("indicator", params.indicator);
  if (params?.window !== undefined) query.set("window", String(params.window));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  const suffix = query.toString();
  return request(`/api/stock/${symbol}/indicators${suffix ? `?${suffix}` : ""}`);
}

export async function getStockDaily(symbol: string, params?: {
  start?: string;
  end?: string;
  min_volume?: number;
  sort?: "asc" | "desc";
}) {
  const query = new URLSearchParams();
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  if (params?.min_volume !== undefined) query.set("min_volume", String(params.min_volume));
  if (params?.sort) query.set("sort", params.sort);
  const suffix = query.toString();
  return request(`/api/stock/${symbol}/daily${suffix ? `?${suffix}` : ""}`);
}

export async function getEventStats(params?: {
  symbol?: string;
  symbols?: string[];
  type?: string;
  event_types?: string[];
  start?: string;
  end?: string;
  granularity?: "day" | "week" | "month";
  top_date?: number;
  top_type?: number;
  top_symbol?: number;
}) {
  const query = new URLSearchParams();
  if (params?.symbol) query.set("symbol", params.symbol);
  params?.symbols?.forEach((item) => query.append("symbols", item));
  if (params?.type) query.set("type", params.type);
  params?.event_types?.forEach((item) => query.append("event_types", item));
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  if (params?.granularity) query.set("granularity", params.granularity);
  if (params?.top_date !== undefined) query.set("top_date", String(params.top_date));
  if (params?.top_type !== undefined) query.set("top_type", String(params.top_type));
  if (params?.top_symbol !== undefined) query.set("top_symbol", String(params.top_symbol));
  return request(`/api/events/stats?${query.toString()}`);
}

export async function getNewsStats(params?: {
  symbol?: string;
  symbols?: string[];
  sentiment?: string;
  sentiments?: string[];
  start?: string;
  end?: string;
  granularity?: "day" | "week" | "month";
  top_date?: number;
  top_sentiment?: number;
  top_symbol?: number;
}) {
  const query = new URLSearchParams();
  if (params?.symbol) query.set("symbol", params.symbol);
  params?.symbols?.forEach((item) => query.append("symbols", item));
  if (params?.sentiment) query.set("sentiment", params.sentiment);
  params?.sentiments?.forEach((item) => query.append("sentiments", item));
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  if (params?.granularity) query.set("granularity", params.granularity);
  if (params?.top_date !== undefined) query.set("top_date", String(params.top_date));
  if (params?.top_sentiment !== undefined) query.set("top_sentiment", String(params.top_sentiment));
  if (params?.top_symbol !== undefined) query.set("top_symbol", String(params.top_symbol));
  return request(`/api/news/stats?${query.toString()}`);
}

export async function getIndexConstituents(symbol: string, params?: { as_of?: string; limit?: number; offset?: number }) {
  const query = new URLSearchParams();
  if (params?.as_of) query.set("as_of", params.as_of);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request(`/api/index/${encodeURIComponent(symbol)}/constituents${suffix ? `?${suffix}` : ""}`);
}

export async function getStock(symbol: string) {
    return request(`/api/stock/${symbol}`);
}

export type StockQuoteResponse = {
  current?: number | null;
  change?: number | null;
  percent?: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  last_close?: number | null;
  volume?: number | null;
  amount?: number | null;
  turnover_rate?: number | null;
  amplitude?: number | null;
  timestamp?: string | null;
};

export type StockQuoteDetailResponse = {
  pe_ttm?: number | null;
  pb?: number | null;
  ps_ttm?: number | null;
  pcf?: number | null;
  market_cap?: number | null;
  float_market_cap?: number | null;
  dividend_yield?: number | null;
  volume_ratio?: number | null;
  lot_size?: number | null;
};

export type StockPankouLevelResponse = {
  level: number;
  price?: number | null;
  volume?: number | null;
};

export type StockPankouResponse = {
  diff?: number | null;
  ratio?: number | null;
  timestamp?: string | null;
  bids?: StockPankouLevelResponse[];
  asks?: StockPankouLevelResponse[];
};

export type StockFundamentalResponse = {
  symbol: string;
  score: number;
  summary: string;
  updated_at: string;
} | null;

export type StockProfileResponse = {
  symbol: string;
  name: string;
  market: string;
  sector: string;
  quote?: StockQuoteResponse | null;
  quote_detail?: StockQuoteDetailResponse | null;
  pankou?: StockPankouResponse | null;
  risk?: {
    symbol: string;
    max_drawdown?: number | null;
    volatility?: number | null;
    as_of?: string | null;
    cache_hit?: boolean | null;
  } | null;
  fundamental?: StockFundamentalResponse;
};

export type StockCompareItem = {
  symbol: string;
  name: string;
  market: string;
  sector: string;
  quote?: StockQuoteResponse | null;
  error?: string | null;
};

export type StockCompareResponse = {
  items: StockCompareItem[];
};

export async function getStockProfilePanel(
  symbol: string,
  params?: { prefer_live?: boolean; refresh_key?: string | number },
  options?: ApiQueryOptions,
) {
  const query = new URLSearchParams();
  if (params?.prefer_live) query.set("prefer_live", "true");
  if (params?.refresh_key !== undefined) query.set("_ts", String(params.refresh_key));
  const suffix = query.toString();
  return request<StockProfileResponse>(
    `/api/stock/${encodeURIComponent(symbol)}/profile${suffix ? `?${suffix}` : ""}`,
    options,
  );
}

export async function getCompareStocks(
  payload: { symbols: string[]; prefer_live?: boolean },
  options?: { retry?: number; retryDelayMs?: number },
) {
  return requestJson<StockCompareResponse>(
    "/api/stock/compare",
    {
      symbols: payload.symbols,
      prefer_live: payload.prefer_live ?? false,
    },
    {
      method: "POST",
      retry: options?.retry ?? 1,
      retryDelayMs: options?.retryDelayMs,
    },
  );
}

export async function getStockOverview(
  symbol: string,
  params?: { prefer_live?: boolean; refresh_key?: string | number }
) {
  const query = new URLSearchParams();
  if (params?.prefer_live) query.set("prefer_live", "true");
  if (params?.refresh_key !== undefined) query.set("_ts", String(params.refresh_key));
  const suffix = query.toString();
  return request(`/api/stock/${encodeURIComponent(symbol)}/overview${suffix ? `?${suffix}` : ""}`);
}

export async function getStockExtras(
  symbol: string,
  params?: { prefer_live?: boolean; refresh_key?: string | number }
) {
  const query = new URLSearchParams();
  if (params?.prefer_live) query.set("prefer_live", "true");
  if (params?.refresh_key !== undefined) query.set("_ts", String(params.refresh_key));
  const suffix = query.toString();
  return request(`/api/stock/${encodeURIComponent(symbol)}/extras${suffix ? `?${suffix}` : ""}`);
}

export async function getFundamental(symbol: string) {
  return request(`/api/stock/${symbol}/fundamental`);
}

export async function getStockFinancials(symbol: string, params?: {
  period?: string;
  min_revenue?: number;
  min_net_income?: number;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.period) query.set("period", params.period);
  if (params?.min_revenue !== undefined) query.set("min_revenue", String(params.min_revenue));
  if (params?.min_net_income !== undefined) query.set("min_net_income", String(params.min_net_income));
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request(`/api/stock/${encodeURIComponent(symbol)}/financials${suffix ? `?${suffix}` : ""}`);
}

export async function getStockResearch(symbol: string, params?: {
  report_limit?: number;
  forecast_limit?: number;
}) {
  const query = new URLSearchParams();
  if (params?.report_limit !== undefined) query.set("report_limit", String(params.report_limit));
  if (params?.forecast_limit !== undefined) query.set("forecast_limit", String(params.forecast_limit));
  const suffix = query.toString();
  return request(`/api/stock/${encodeURIComponent(symbol)}/research${suffix ? `?${suffix}` : ""}`);
}

export async function getNews(symbol: string, params?: { limit?: number; offset?: number }) {
  const query = new URLSearchParams();
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request(`/api/stock/${symbol}/news${suffix ? `?${suffix}` : ""}`);
}

export async function getEventTimeline(params?: {
  symbol?: string;
  symbols?: string[];
  type?: string;
  types?: string[];
  keyword?: string;
  sort_by?: string[];
  start?: string;
  end?: string;
  limit?: number;
  offset?: number;
  sort?: "asc" | "desc";
}) {
  const query = new URLSearchParams();
  if (params?.symbol) query.set("symbol", params.symbol);
  params?.symbols?.forEach((item) => query.append("symbols", item));
  if (params?.type) query.set("type", params.type);
  params?.types?.forEach((item) => query.append("event_types", item));
  if (params?.keyword) query.set("keyword", params.keyword);
  params?.sort_by?.forEach((item) => query.append("sort_by", item));
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  if (params?.sort) query.set("sort", params.sort);
  return request(`/api/events/timeline?${query.toString()}`);
}

export async function getNewsAggregate(params?: {
  symbol?: string;
  symbols?: string[];
  sentiment?: string;
  sentiments?: string[];
  source_site?: string;
  source_sites?: string[];
  source_category?: string;
  source_categories?: string[];
  topic_category?: string;
  topic_categories?: string[];
  time_bucket?: string;
  time_buckets?: string[];
  related_symbol?: string;
  related_symbols?: string[];
  related_sector?: string;
  related_sectors?: string[];
  keyword?: string;
  sort_by?: string[];
  start?: string;
  end?: string;
  limit?: number;
  offset?: number;
  sort?: "asc" | "desc";
}) {
  const query = new URLSearchParams();
  if (params?.symbol) query.set("symbol", params.symbol);
  params?.symbols?.forEach((item) => query.append("symbols", item));
  if (params?.sentiment) query.set("sentiment", params.sentiment);
  params?.sentiments?.forEach((item) => query.append("sentiments", item));
  if (params?.source_site) query.set("source_site", params.source_site);
  params?.source_sites?.forEach((item) => query.append("source_sites", item));
  if (params?.source_category) query.set("source_category", params.source_category);
  params?.source_categories?.forEach((item) => query.append("source_categories", item));
  if (params?.topic_category) query.set("topic_category", params.topic_category);
  params?.topic_categories?.forEach((item) => query.append("topic_categories", item));
  if (params?.time_bucket) query.set("time_bucket", params.time_bucket);
  params?.time_buckets?.forEach((item) => query.append("time_buckets", item));
  if (params?.related_symbol) query.set("related_symbol", params.related_symbol);
  params?.related_symbols?.forEach((item) => query.append("related_symbols", item));
  if (params?.related_sector) query.set("related_sector", params.related_sector);
  params?.related_sectors?.forEach((item) => query.append("related_sectors", item));
  if (params?.keyword) query.set("keyword", params.keyword);
  params?.sort_by?.forEach((item) => query.append("sort_by", item));
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  if (params?.sort) query.set("sort", params.sort);
  return request(`/api/news/aggregate?${query.toString()}`);
}

export async function getHeatmap(params?: {
  sector?: string;
  market?: string;
  min_change?: number;
  max_change?: number;
  as_of?: string;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.sector) query.set("sector", params.sector);
  if (params?.market) query.set("market", params.market);
  if (params?.min_change !== undefined) query.set("min_change", String(params.min_change));
  if (params?.max_change !== undefined) query.set("max_change", String(params.max_change));
  if (params?.as_of) query.set("as_of", params.as_of);
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request(`/api/heatmap${suffix ? `?${suffix}` : ""}`);
}

export async function getMacro(params?: {
  start?: string;
  end?: string;
  as_of?: string;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  if (params?.as_of) query.set("as_of", params.as_of);
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request(`/api/macro${suffix ? `?${suffix}` : ""}`);
}

export async function getMacroSnapshot(params?: {
  as_of?: string;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  const limit = params?.limit !== undefined ? Math.min(Math.max(1, Math.trunc(params.limit)), 200) : undefined;
  if (params?.as_of) query.set("as_of", params.as_of);
  if (params?.sort) query.set("sort", params.sort);
  if (limit !== undefined) query.set("limit", String(limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request<ApiPage<{ key: string; date: string; value: number; score?: number }>>(
    `/api/macro/snapshot${suffix ? `?${suffix}` : ""}`,
  );
}

export async function getMacroSeries(key: string, params?: { start?: string; end?: string }) {
  const query = new URLSearchParams();
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  const suffix = query.toString();
  return request(`/api/macro/series/${encodeURIComponent(key)}${suffix ? `?${suffix}` : ""}`);
}

export async function getSectorExposure(params?: {
  market?: string;
  basis?: string;
  limit?: number;
  offset?: number;
  sort?: "asc" | "desc";
  as_of?: string;
}) {
  const query = new URLSearchParams();
  if (params?.market) query.set("market", params.market);
  if (params?.basis) query.set("basis", params.basis);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  if (params?.sort) query.set("sort", params.sort);
  if (params?.as_of) query.set("as_of", params.as_of);
  const suffix = query.toString();
  return request(`/api/sector/exposure${suffix ? `?${suffix}` : ""}`);
}

export type BondMarketQuoteItem = {
  quote_org?: string | null;
  bond_name: string;
  buy_net_price?: number | null;
  sell_net_price?: number | null;
  buy_yield?: number | null;
  sell_yield?: number | null;
  as_of?: string | null;
  source?: string | null;
};

export type BondMarketTradeItem = {
  bond_name: string;
  deal_net_price?: number | null;
  latest_yield?: number | null;
  change?: number | null;
  weighted_yield?: number | null;
  volume?: number | null;
  as_of?: string | null;
  source?: string | null;
};

export type FxSpotQuoteItem = {
  currency_pair: string;
  bid?: number | null;
  ask?: number | null;
  as_of?: string | null;
  source?: string | null;
};

export type FxSwapQuoteItem = {
  currency_pair: string;
  one_week?: number | null;
  one_month?: number | null;
  three_month?: number | null;
  six_month?: number | null;
  nine_month?: number | null;
  one_year?: number | null;
  as_of?: string | null;
  source?: string | null;
};

export type FxPairQuoteItem = {
  currency_pair: string;
  bid?: number | null;
  ask?: number | null;
  as_of?: string | null;
  source?: string | null;
};

export async function getBondMarketQuotes(params?: {
  keyword?: string;
  refresh?: boolean;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.keyword) query.set("keyword", params.keyword);
  if (params?.refresh) query.set("refresh", "true");
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request<ApiPage<BondMarketQuoteItem>>(`/api/bond/market/quote${suffix ? `?${suffix}` : ""}`);
}

export async function getBondMarketTrades(params?: {
  keyword?: string;
  refresh?: boolean;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.keyword) query.set("keyword", params.keyword);
  if (params?.refresh) query.set("refresh", "true");
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request<ApiPage<BondMarketTradeItem>>(`/api/bond/market/trade${suffix ? `?${suffix}` : ""}`);
}

export async function getFxSpotQuotes(params?: {
  pair?: string;
  refresh?: boolean;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.pair) query.set("pair", params.pair);
  if (params?.refresh) query.set("refresh", "true");
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request<ApiPage<FxSpotQuoteItem>>(`/api/fx/spot${suffix ? `?${suffix}` : ""}`);
}

export async function getFxSwapQuotes(params?: {
  pair?: string;
  refresh?: boolean;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.pair) query.set("pair", params.pair);
  if (params?.refresh) query.set("refresh", "true");
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request<ApiPage<FxSwapQuoteItem>>(`/api/fx/swap${suffix ? `?${suffix}` : ""}`);
}

export async function getFxPairQuotes(params?: {
  pair?: string;
  refresh?: boolean;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.pair) query.set("pair", params.pair);
  if (params?.refresh) query.set("refresh", "true");
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request<ApiPage<FxPairQuoteItem>>(`/api/fx/pair${suffix ? `?${suffix}` : ""}`);
}

export async function getPortfolioAnalysis(userId: number, params?: { top_n?: number }) {
  const query = new URLSearchParams();
  if (params?.top_n !== undefined) query.set("top_n", String(params.top_n));
  const suffix = query.toString();
  return request(`/api/user/${userId}/portfolio/analysis${suffix ? `?${suffix}` : ""}`);
}

export type WatchTargetItem = {
  symbol: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type BoughtTargetItem = {
  symbol: string;
  buy_price: number;
  lots: number;
  buy_date: string;
  fee: number;
  note: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type AlertRuleType = "price" | "event" | "earnings";
export type AlertPriceOperator = "gte" | "lte";
export type AlertResearchKind = "all" | "report" | "earning_forecast";

export type AlertRuleItem = {
  id: number;
  name: string;
  rule_type: AlertRuleType;
  symbol: string;
  price_operator?: AlertPriceOperator | null;
  threshold?: number | null;
  event_type?: string | null;
  research_kind?: AlertResearchKind | null;
  lookback_days: number;
  is_active: boolean;
  note: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type AlertCenterItem = AlertRuleItem & {
  triggered: boolean;
  status: string;
  status_message: string;
  latest_value?: number | null;
  matched_at?: string | null;
  context_title?: string | null;
};

export type AlertCenterResponse = {
  total: number;
  triggered: number;
  items: AlertCenterItem[];
};

export type UserStockPoolItem = {
  id: number;
  name: string;
  market: "A" | "HK" | "US";
  symbols: string[];
  note: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type UserStockFilterItem = {
  id: number;
  name: string;
  market: "A" | "HK" | "US";
  keyword: string;
  sector: string;
  sort: "asc" | "desc";
  created_at?: string | null;
  updated_at?: string | null;
};

export type UserWorkspaceResponse = {
  pools: UserStockPoolItem[];
  filters: UserStockFilterItem[];
};

export async function registerUser(account: string, password: string) {
  return requestJson("/api/auth/register", { account, password });
}

export async function loginUser(account: string, password: string) {
  return requestJson("/api/auth/login", { account, password });
}

export async function getCurrentUser(token: string) {
  return requestAuthed("/api/auth/me", token);
}

export async function getMyWatchTargets(token: string) {
  return requestAuthed<WatchTargetItem[]>("/api/user/me/watch-targets", token);
}

export async function upsertMyWatchTarget(token: string, symbol: string) {
  return requestAuthedJson<WatchTargetItem>("/api/user/me/watch-targets", { symbol }, token);
}

export async function upsertMyWatchTargetsBatch(token: string, symbols: string[]) {
  return requestAuthedJson<WatchTargetItem[]>(
    "/api/user/me/watch-targets/batch",
    { symbols },
    token,
  );
}

export async function deleteMyWatchTarget(token: string, symbol: string) {
  return requestAuthedDelete(`/api/user/me/watch-targets/${encodeURIComponent(symbol)}`, token);
}

export async function getMyBoughtTargets(token: string) {
  return requestAuthed<BoughtTargetItem[]>("/api/user/me/bought-targets", token);
}

export async function upsertMyBoughtTarget(
  token: string,
  payload: { symbol: string; buy_price: number; lots: number; buy_date: string; fee?: number; note?: string },
) {
  return requestAuthedJson<BoughtTargetItem>(
    "/api/user/me/bought-targets",
    {
      symbol: payload.symbol,
      buy_price: payload.buy_price,
      lots: payload.lots,
      buy_date: payload.buy_date,
      fee: payload.fee ?? 0,
      note: payload.note ?? "",
    },
    token,
  );
}

export async function upsertMyBoughtTargetsBatch(
  token: string,
  items: Array<{ symbol: string; buy_price: number; lots: number; buy_date: string; fee?: number; note?: string }>,
) {
  return requestAuthedJson<BoughtTargetItem[]>(
    "/api/user/me/bought-targets/batch",
    {
      items: items.map((item) => ({
        symbol: item.symbol,
        buy_price: item.buy_price,
        lots: item.lots,
        buy_date: item.buy_date,
        fee: item.fee ?? 0,
        note: item.note ?? "",
      })),
    },
    token,
  );
}

export async function deleteMyBoughtTarget(token: string, symbol: string) {
  return requestAuthedDelete(`/api/user/me/bought-targets/${encodeURIComponent(symbol)}`, token);
}

export async function getMyAlerts(token: string) {
  return requestAuthed<AlertRuleItem[]>("/api/user/me/alerts", token);
}

export async function getMyAlertCenter(token: string) {
  return requestAuthed<AlertCenterResponse>("/api/user/me/alerts/center", token);
}

export async function createMyAlert(
  token: string,
  payload: {
    name: string;
    rule_type: AlertRuleType;
    symbol: string;
    price_operator?: AlertPriceOperator;
    threshold?: number;
    event_type?: string;
    research_kind?: AlertResearchKind;
    lookback_days?: number;
    is_active?: boolean;
    note?: string;
  },
) {
  return requestAuthedJson<AlertRuleItem>(
    "/api/user/me/alerts",
    {
      ...payload,
      lookback_days: payload.lookback_days ?? 7,
      is_active: payload.is_active ?? true,
      note: payload.note ?? "",
    },
    token,
  );
}

export async function updateMyAlert(
  token: string,
  ruleId: number,
  payload: {
    name?: string;
    price_operator?: AlertPriceOperator;
    threshold?: number;
    event_type?: string;
    research_kind?: AlertResearchKind;
    lookback_days?: number;
    is_active?: boolean;
    note?: string;
  },
) {
  return requestAuthedJson<AlertRuleItem>(`/api/user/me/alerts/${ruleId}`, payload, token, { method: "PATCH" });
}

export async function deleteMyAlert(token: string, ruleId: number) {
  return requestAuthedDelete(`/api/user/me/alerts/${ruleId}`, token);
}

export async function getMyWorkspace(token: string) {
  return requestAuthed<UserWorkspaceResponse>("/api/user/me/workspace", token);
}

export async function createMyStockPool(
  token: string,
  payload: { name: string; market: "A" | "HK" | "US"; symbols: string[]; note?: string },
) {
  return requestAuthedJson<UserStockPoolItem>(
    "/api/user/me/stock-pools",
    {
      name: payload.name,
      market: payload.market,
      symbols: payload.symbols,
      note: payload.note ?? "",
    },
    token,
  );
}

export async function deleteMyStockPool(token: string, poolId: number) {
  return requestAuthedDelete(`/api/user/me/stock-pools/${poolId}`, token);
}

export async function createMyStockFilter(
  token: string,
  payload: { name: string; market: "A" | "HK" | "US"; keyword?: string; sector?: string; sort?: "asc" | "desc" },
) {
  return requestAuthedJson<UserStockFilterItem>(
    "/api/user/me/stock-filters",
    {
      name: payload.name,
      market: payload.market,
      keyword: payload.keyword ?? "",
      sector: payload.sector ?? "",
      sort: payload.sort ?? "asc",
    },
    token,
  );
}

export async function deleteMyStockFilter(token: string, filterId: number) {
  return requestAuthedDelete(`/api/user/me/stock-filters/${filterId}`, token);
}

