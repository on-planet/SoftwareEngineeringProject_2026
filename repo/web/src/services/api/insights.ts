import { ApiPage, request } from "./core";

type CacheMeta = {
  cache_hit?: boolean | null;
  as_of?: string | null;
  refresh_queued?: boolean | null;
};

export type NewsItemResponse = {
  id: number;
  symbol: string;
  title: string;
  sentiment: string;
  published_at: string;
  link?: string | null;
  source?: string | null;
  source_site?: string | null;
  source_category?: string | null;
  topic_category?: string | null;
  time_bucket?: string | null;
  related_symbols?: string[];
  related_sectors?: string[];
  event_type?: string | null;
  event_tags?: string[];
  themes?: string[];
  impact_direction?: string | null;
  nlp_confidence?: number | null;
  nlp_version?: string | null;
  keywords?: string[];
};

export type NewsGraphNode = {
  id: string;
  type: string;
  label: string;
  size: number;
  sentiment?: string | null;
  metadata: Record<string, unknown>;
};

export type NewsGraphEdge = {
  source: string;
  target: string;
  type: string;
  weight: number;
  label?: string | null;
};

export type NewsGraphExplanation = {
  headline: string;
  evidence: string[];
  risk_hint?: string | null;
  generated_by: string;
};

export type NewsGraphEntity = {
  id: string;
  type: string;
  label: string;
  sentiment?: string | null;
};

export type NewsGraphChainStep = NewsGraphEntity & {
  relation?: string | null;
  weight?: number | null;
};

export type NewsGraphChain = {
  id: string;
  title: string;
  summary?: string | null;
  strength: number;
  steps: NewsGraphChainStep[];
};

export type NewsGraphEvent = {
  id: number;
  symbol: string;
  type: string;
  title: string;
  date: string;
  link?: string | null;
  source?: string | null;
};

export type NewsGraphImpactSummary = {
  related_news_count: number;
  related_event_count: number;
  propagation_chain_count: number;
  impact_chain_count: number;
  dominant_sentiment: string;
  dominant_direction?: string | null;
  affected_symbols: NewsGraphEntity[];
  affected_sectors: NewsGraphEntity[];
  portfolio_hint?: string | null;
};

export type NewsGraphResponse = {
  center_type: string;
  center_id: string;
  center_label: string;
  days: number;
  nodes: NewsGraphNode[];
  edges: NewsGraphEdge[];
  explanation: NewsGraphExplanation;
  related_news: NewsItemResponse[];
  related_events: NewsGraphEvent[];
  propagation_chains: NewsGraphChain[];
  impact_chains: NewsGraphChain[];
  impact_summary: NewsGraphImpactSummary;
};

export type EventStatsResponse = CacheMeta & {
  by_date: Array<{ date: string; count: number }>;
  by_type: Array<{ type: string; count: number }>;
  by_symbol: Array<{ symbol: string; count: number }>;
};

export type NewsStatsResponse = CacheMeta & {
  by_date: Array<{ date: string; count: number }>;
  by_sentiment: Array<{ sentiment: string; count: number }>;
  by_symbol: Array<{ symbol: string; count: number }>;
};

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
  return request<EventStatsResponse>(`/api/events/stats?${query.toString()}`);
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
  return request<NewsStatsResponse>(`/api/news/stats?${query.toString()}`);
}

export async function getNews(symbol: string, params?: { limit?: number; offset?: number }) {
  const query = new URLSearchParams();
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request<ApiPage<NewsItemResponse>>(`/api/stock/${encodeURIComponent(symbol)}/news${suffix ? `?${suffix}` : ""}`);
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
  return request<ApiPage<NewsItemResponse>>(`/api/news/aggregate?${query.toString()}`);
}

export async function getStockNewsGraph(
  symbol: string,
  params?: {
    days?: number;
    limit?: number;
  },
) {
  const query = new URLSearchParams();
  if (params?.days !== undefined) query.set("days", String(params.days));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const suffix = query.toString();
  return request<NewsGraphResponse>(`/api/news/graph/stock/${encodeURIComponent(symbol)}${suffix ? `?${suffix}` : ""}`, {
    label: "news-graph-stock",
  });
}

export async function getNewsFocusGraph(
  newsId: number,
  params?: {
    days?: number;
    limit?: number;
  },
) {
  const query = new URLSearchParams();
  if (params?.days !== undefined) query.set("days", String(params.days));
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  const suffix = query.toString();
  return request<NewsGraphResponse>(`/api/news/graph/${newsId}${suffix ? `?${suffix}` : ""}`, {
    label: "news-graph-focus",
  });
}
