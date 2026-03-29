import { ApiQueryOptions, request, requestJson } from "./core";

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

export type IndexInsightConstituentItem = {
  index_symbol: string;
  symbol: string;
  date?: string | null;
  weight?: number | null;
  name?: string | null;
  market?: string | null;
  sector?: string | null;
  rank?: number | null;
  current?: number | null;
  change?: number | null;
  percent?: number | null;
  contribution_change?: number | null;
  contribution_score?: number | null;
  source?: string | null;
};

export type IndexInsightSectorItem = {
  sector: string;
  weight: number;
  symbol_count: number;
  avg_percent?: number | null;
  leader_symbol?: string | null;
  leader_name?: string | null;
};

export type IndexInsightSummary = {
  symbol: string;
  name: string;
  market: string;
  as_of?: string | null;
  constituent_total: number;
  priced_total: number;
  weight_coverage: number;
  top5_weight: number;
  top10_weight: number;
  rising_count: number;
  falling_count: number;
  flat_count: number;
};

export type IndexInsightResponse = {
  summary: IndexInsightSummary;
  top_weights: IndexInsightConstituentItem[];
  top_contributors: IndexInsightConstituentItem[];
  top_detractors: IndexInsightConstituentItem[];
  sector_breakdown: IndexInsightSectorItem[];
  constituents: IndexInsightConstituentItem[];
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

export type StockOverviewResponse = {
  symbol: string;
  name: string;
  market: string;
  sector: string;
  quote?: StockQuoteResponse | null;
  risk?: StockProfileResponse["risk"];
  fundamental?: StockFundamentalResponse;
};

export type StockExtrasResponse = {
  symbol: string;
  quote_detail?: StockQuoteDetailResponse | null;
  pankou?: StockPankouResponse | null;
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

export async function getIndices(params?: { as_of?: string; sort?: "asc" | "desc"; limit?: number; offset?: number }) {
  const query = new URLSearchParams();
  if (params?.as_of) query.set("as_of", params.as_of);
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request(`/api/index${suffix ? `?${suffix}` : ""}`, { label: "indices" });
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
  return request<KlineSeriesResponse>(
    `/api/index/${encodeURIComponent(symbol)}/kline${suffix ? `?${suffix}` : ""}`,
    {
      label: "index-kline",
    },
  );
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
  return request<KlineSeriesResponse>(
    `/api/stock/${encodeURIComponent(symbol)}/kline${suffix ? `?${suffix}` : ""}`,
    {
      label: "stock-kline",
    },
  );
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
  return request(`/api/risk/${encodeURIComponent(symbol)}`);
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
  return request(`/api/risk/${encodeURIComponent(symbol)}/series${suffix ? `?${suffix}` : ""}`);
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
  return request(`/api/stock/${encodeURIComponent(symbol)}/indicators${suffix ? `?${suffix}` : ""}`);
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
  return request(`/api/stock/${encodeURIComponent(symbol)}/daily${suffix ? `?${suffix}` : ""}`);
}

export async function getIndexConstituents(symbol: string, params?: { as_of?: string; limit?: number; offset?: number }) {
  const query = new URLSearchParams();
  if (params?.as_of) query.set("as_of", params.as_of);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request(`/api/index/${encodeURIComponent(symbol)}/constituents${suffix ? `?${suffix}` : ""}`);
}

export async function getIndexInsights(symbol: string, params?: { as_of?: string }) {
  const query = new URLSearchParams();
  if (params?.as_of) query.set("as_of", params.as_of);
  const suffix = query.toString();
  return request<IndexInsightResponse>(`/api/index/${encodeURIComponent(symbol)}/insights${suffix ? `?${suffix}` : ""}`);
}

export async function getStock(symbol: string) {
  return request(`/api/stock/${encodeURIComponent(symbol)}`);
}

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
  return request<StockOverviewResponse>(
    `/api/stock/${encodeURIComponent(symbol)}/overview${suffix ? `?${suffix}` : ""}`,
    { label: "stock-overview" },
  );
}

export async function getStockExtras(
  symbol: string,
  params?: { prefer_live?: boolean; refresh_key?: string | number }
) {
  const query = new URLSearchParams();
  if (params?.prefer_live) query.set("prefer_live", "true");
  if (params?.refresh_key !== undefined) query.set("_ts", String(params.refresh_key));
  const suffix = query.toString();
  return request<StockExtrasResponse>(
    `/api/stock/${encodeURIComponent(symbol)}/extras${suffix ? `?${suffix}` : ""}`,
    { label: "stock-extras" },
  );
}

export async function getFundamental(symbol: string) {
  return request(`/api/stock/${encodeURIComponent(symbol)}/fundamental`);
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
