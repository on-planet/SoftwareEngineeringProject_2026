import {
  ApiQueryOptions,
  DashboardStatsOverviewQuery,
  DashboardStatsOverviewResponse,
  getDashboardStatsOverview,
} from "../services/api";

const STATS_OVERVIEW_STALE_TIME_MS = 60_000;
const STATS_OVERVIEW_CACHE_TIME_MS = 5 * 60_000;

export type StatsOverviewGranularity = "day" | "week" | "month";

export type StatsOverviewParams = {
  symbol?: string;
  symbols?: string[];
  start?: string;
  end?: string;
  granularity: StatsOverviewGranularity;
  topDate: number;
  topType: number;
  topSymbol: number;
  topSentiment: number;
};

export function normalizeStatsSymbols(values: string[] | undefined) {
  if (!values || values.length === 0) {
    return [];
  }
  const unique = new Set<string>();
  const output: string[] = [];
  values.forEach((value) => {
    const symbol = (value || "").trim().toUpperCase();
    if (!symbol || unique.has(symbol)) {
      return;
    }
    unique.add(symbol);
    output.push(symbol);
  });
  return output;
}

export function buildStatsOverviewQueryKey(params: StatsOverviewParams) {
  return [
    "dashboard-stats-overview",
    `symbol=${params.symbol || "all"}`,
    `symbols=${normalizeStatsSymbols(params.symbols).join(",") || "none"}`,
    `start=${params.start || "none"}`,
    `end=${params.end || "none"}`,
    `granularity=${params.granularity}`,
    `topDate=${params.topDate}`,
    `topType=${params.topType}`,
    `topSymbol=${params.topSymbol}`,
    `topSentiment=${params.topSentiment}`,
  ].join(":");
}

export function getStatsOverviewQueryOptions(cacheKey: string): ApiQueryOptions {
  return {
    staleTimeMs: STATS_OVERVIEW_STALE_TIME_MS,
    cacheTimeMs: STATS_OVERVIEW_CACHE_TIME_MS,
    persist: {
      key: cacheKey,
      maxAgeMs: STATS_OVERVIEW_CACHE_TIME_MS,
    },
    label: "dashboard-stats-overview",
  };
}

export async function loadStatsOverview(params: StatsOverviewParams) {
  return getDashboardStatsOverview({
    symbol: params.symbol || undefined,
    symbols: normalizeStatsSymbols(params.symbols),
    start: params.start || undefined,
    end: params.end || undefined,
    granularity: params.granularity,
    top_date: params.topDate || undefined,
    top_type: params.topType || undefined,
    top_sentiment: params.topSentiment || undefined,
    top_symbol: params.topSymbol || undefined,
  });
}

export function normalizeStatsOverviewResponse(
  response: DashboardStatsOverviewResponse | undefined,
  params: StatsOverviewParams,
): DashboardStatsOverviewResponse {
  const query: DashboardStatsOverviewQuery = {
    symbols: response?.query?.symbols ?? normalizeStatsSymbols(params.symbols),
    event_types: response?.query?.event_types ?? [],
    sentiments: response?.query?.sentiments ?? [],
    start: response?.query?.start ?? params.start ?? null,
    end: response?.query?.end ?? params.end ?? null,
    granularity: response?.query?.granularity ?? params.granularity,
    top_date: response?.query?.top_date ?? params.topDate,
    top_type: response?.query?.top_type ?? params.topType,
    top_sentiment: response?.query?.top_sentiment ?? params.topSentiment,
    top_symbol: response?.query?.top_symbol ?? params.topSymbol,
  };

  return {
    schema_version: response?.schema_version ?? "dashboard-stats-overview.v1",
    query,
    cache_hit: response?.cache_hit ?? null,
    as_of: response?.as_of ?? null,
    refresh_queued: response?.refresh_queued ?? null,
    events: {
      by_date: response?.events?.by_date ?? [],
      by_type: response?.events?.by_type ?? [],
      by_symbol: response?.events?.by_symbol ?? [],
      cache_hit: response?.events?.cache_hit ?? null,
      as_of: response?.events?.as_of ?? null,
      refresh_queued: response?.events?.refresh_queued ?? null,
    },
    news: {
      by_date: response?.news?.by_date ?? [],
      by_sentiment: response?.news?.by_sentiment ?? [],
      by_symbol: response?.news?.by_symbol ?? [],
      cache_hit: response?.news?.cache_hit ?? null,
      as_of: response?.news?.as_of ?? null,
      refresh_queued: response?.news?.refresh_queued ?? null,
    },
  };
}
