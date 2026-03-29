import { ApiPage, request } from "./core";

import type { NewsItemResponse } from "./insights";

type CacheMeta = {
  cache_hit?: boolean | null;
  as_of?: string | null;
  refresh_queued?: boolean | null;
};

export type DashboardIndexItem = {
  symbol: string;
  name?: string | null;
  market?: string | null;
  date: string;
  close: number;
  change: number;
};

export type DashboardHeatmapItem = {
  sector: string;
  avg_close: number;
  avg_change: number;
};

export type DashboardMacroSnapshotItem = {
  key: string;
  date: string;
  value: number;
  score?: number | null;
};

export type DashboardFuturesItem = {
  symbol: string;
  name?: string | null;
  date: string;
  contract_month?: string | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
  settlement?: number | null;
  open_interest?: number | null;
  turnover?: number | null;
  volume?: number | null;
  source?: string | null;
};

export type DashboardEventStatsResponse = CacheMeta & {
  by_date: Array<{ date: string; count: number }>;
  by_type: Array<{ type: string; count: number }>;
  by_symbol: Array<{ symbol: string; count: number }>;
};

export type DashboardNewsStatsResponse = CacheMeta & {
  by_date: Array<{ date: string; count: number }>;
  by_sentiment: Array<{ sentiment: string; count: number }>;
  by_symbol: Array<{ symbol: string; count: number }>;
};

export type DashboardOverviewQuery = {
  as_of?: string | null;
  index_limit: number;
  heatmap_limit: number;
  macro_limit: number;
  futures_limit: number;
  news_limit: number;
};

export type DashboardOverviewResponse = CacheMeta & {
  schema_version: "dashboard-overview.v1";
  query: DashboardOverviewQuery;
  indices: ApiPage<DashboardIndexItem>;
  heatmap: {
    a: ApiPage<DashboardHeatmapItem>;
    hk: ApiPage<DashboardHeatmapItem>;
  };
  macro_snapshot: ApiPage<DashboardMacroSnapshotItem>;
  futures: ApiPage<DashboardFuturesItem>;
  top_news: ApiPage<NewsItemResponse>;
};

export type DashboardStatsOverviewQuery = {
  symbols: string[];
  event_types: string[];
  sentiments: string[];
  start?: string | null;
  end?: string | null;
  granularity: "day" | "week" | "month";
  top_date?: number | null;
  top_type?: number | null;
  top_sentiment?: number | null;
  top_symbol?: number | null;
};

export type DashboardStatsOverviewResponse = CacheMeta & {
  schema_version: "dashboard-stats-overview.v1";
  query: DashboardStatsOverviewQuery;
  events: DashboardEventStatsResponse;
  news: DashboardNewsStatsResponse;
};

export async function getDashboardOverview(params?: {
  as_of?: string;
  index_limit?: number;
  heatmap_limit?: number;
  macro_limit?: number;
  futures_limit?: number;
  news_limit?: number;
}) {
  const query = new URLSearchParams();
  if (params?.as_of) query.set("as_of", params.as_of);
  if (params?.index_limit !== undefined) query.set("index_limit", String(params.index_limit));
  if (params?.heatmap_limit !== undefined) query.set("heatmap_limit", String(params.heatmap_limit));
  if (params?.macro_limit !== undefined) query.set("macro_limit", String(params.macro_limit));
  if (params?.futures_limit !== undefined) query.set("futures_limit", String(params.futures_limit));
  if (params?.news_limit !== undefined) query.set("news_limit", String(params.news_limit));
  const suffix = query.toString();
  return request<DashboardOverviewResponse>(`/api/dashboard/overview${suffix ? `?${suffix}` : ""}`, {
    label: "dashboard-overview",
  });
}

export async function getDashboardStatsOverview(params?: {
  symbol?: string;
  symbols?: string[];
  type?: string;
  event_types?: string[];
  sentiment?: string;
  sentiments?: string[];
  start?: string;
  end?: string;
  granularity?: "day" | "week" | "month";
  top_date?: number;
  top_type?: number;
  top_sentiment?: number;
  top_symbol?: number;
}) {
  const query = new URLSearchParams();
  if (params?.symbol) query.set("symbol", params.symbol);
  params?.symbols?.forEach((item) => query.append("symbols", item));
  if (params?.type) query.set("type", params.type);
  params?.event_types?.forEach((item) => query.append("event_types", item));
  if (params?.sentiment) query.set("sentiment", params.sentiment);
  params?.sentiments?.forEach((item) => query.append("sentiments", item));
  if (params?.start) query.set("start", params.start);
  if (params?.end) query.set("end", params.end);
  if (params?.granularity) query.set("granularity", params.granularity);
  if (params?.top_date !== undefined) query.set("top_date", String(params.top_date));
  if (params?.top_type !== undefined) query.set("top_type", String(params.top_type));
  if (params?.top_sentiment !== undefined) query.set("top_sentiment", String(params.top_sentiment));
  if (params?.top_symbol !== undefined) query.set("top_symbol", String(params.top_symbol));
  const suffix = query.toString();
  return request<DashboardStatsOverviewResponse>(`/api/dashboard/stats-overview${suffix ? `?${suffix}` : ""}`, {
    label: "dashboard-stats-overview",
  });
}
