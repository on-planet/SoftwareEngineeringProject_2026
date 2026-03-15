async function request<T = any>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `请求失败: ${res.status}`);
  }
  return res.json() as Promise<T>;
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
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.market) query.set("market", params.market);
  if (params?.keyword) query.set("keyword", params.keyword);
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request(`/api/stocks${suffix ? `?${suffix}` : ""}`);
}

export async function getIndexKline(symbol: string, params?: {
  period?: "day" | "week" | "month" | "quarter" | "year";
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
  return request(`/api/index/${encodeURIComponent(symbol)}/kline${suffix ? `?${suffix}` : ""}`);
}

export async function getStockKline(symbol: string, params?: {
  period?: "day" | "week" | "month" | "quarter" | "year";
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
  return request(`/api/stock/${encodeURIComponent(symbol)}/kline${suffix ? `?${suffix}` : ""}`);
}

export async function getFutures(params?: {
  symbol?: string;
  start?: string;
  end?: string;
  sort?: "asc" | "desc";
  limit?: number;
  offset?: number;
}) {
  const query = new URLSearchParams();
  if (params?.symbol) query.set("symbol", params.symbol);
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  if (params?.sort) query.set("sort", params.sort);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request(`/api/futures${suffix ? `?${suffix}` : ""}`);
}

export async function getFuturesSeries(
  symbol: string,
  params?: { start?: string; end?: string }
) {
  const query = new URLSearchParams();
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
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
  indicator?: "ma" | "rsi";
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
  return request(`/api/index/${symbol}/constituents${suffix ? `?${suffix}` : ""}`);
}

export async function getStock(symbol: string) {
    return request(`/api/stock/${symbol}`);
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

export async function getMacroSeries(key: string, params?: { start?: string; end?: string }) {
  const query = new URLSearchParams();
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  const suffix = query.toString();
  return request(`/api/macro/series/${encodeURIComponent(key)}${suffix ? `?${suffix}` : ""}`);
}

export async function getSectorExposure(params?: {
  market?: string;
  limit?: number;
  offset?: number;
  sort?: "asc" | "desc";
  as_of?: string;
}) {
  const query = new URLSearchParams();
  if (params?.market) query.set("market", params.market);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  if (params?.sort) query.set("sort", params.sort);
  if (params?.as_of) query.set("as_of", params.as_of);
  const suffix = query.toString();
  return request(`/api/sector/exposure${suffix ? `?${suffix}` : ""}`);
}

export async function getPortfolioAnalysis(userId: number, params?: { top_n?: number }) {
  const query = new URLSearchParams();
  if (params?.top_n !== undefined) query.set("top_n", String(params.top_n));
  const suffix = query.toString();
  return request(`/api/user/${userId}/portfolio/analysis${suffix ? `?${suffix}` : ""}`);
}
