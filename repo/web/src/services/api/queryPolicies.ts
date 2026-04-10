import type { ApiQueryOptions } from "./core";

const THIRTY_SECONDS_MS = 30_000;
const ONE_MINUTE_MS = 60_000;
const TWO_MINUTES_MS = 2 * 60_000;
const FIVE_MINUTES_MS = 5 * 60_000;
const TEN_MINUTES_MS = 10 * 60_000;

function hashIdentity(value: string) {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) | 0;
  }
  return Math.abs(hash).toString(36);
}

function buildPersistedQueryOptions(
  cacheKey: string,
  label: string,
  staleTimeMs: number,
  cacheTimeMs: number,
  persistMaxAgeMs = cacheTimeMs,
): ApiQueryOptions {
  return {
    staleTimeMs,
    cacheTimeMs,
    persist: {
      key: cacheKey,
      maxAgeMs: persistMaxAgeMs,
    },
    label,
  };
}

function buildUserScopedKey(token: string, scope: string) {
  return `user:${scope}:${hashIdentity(token)}`;
}

export function buildIndicesQueryKey(asOf?: string) {
  return `market:indices:${asOf || "latest"}`;
}

export function getIndicesQueryOptions(cacheKey: string): ApiQueryOptions {
  return buildPersistedQueryOptions(cacheKey, "indices", ONE_MINUTE_MS, FIVE_MINUTES_MS);
}

export function buildMacroSnapshotQueryKey() {
  return "macro:snapshot:latest";
}

export function getMacroSnapshotQueryOptions(cacheKey: string): ApiQueryOptions {
  return buildPersistedQueryOptions(cacheKey, "macro-snapshot", ONE_MINUTE_MS, FIVE_MINUTES_MS);
}

export function buildMacroSeriesQueryKey(seriesKey: string, start?: string, end?: string) {
  return `macro:series:${seriesKey}:start=${start || "none"}:end=${end || "none"}`;
}

export function getMacroSeriesQueryOptions(cacheKey: string): ApiQueryOptions {
  return buildPersistedQueryOptions(cacheKey, "macro-series", ONE_MINUTE_MS, TEN_MINUTES_MS);
}

export function buildMyWatchTargetsQueryKey(token: string) {
  return buildUserScopedKey(token, "watch-targets");
}

export function buildMyBoughtTargetsQueryKey(token: string) {
  return buildUserScopedKey(token, "bought-targets");
}

export function buildMyAlertCenterQueryKey(token: string) {
  return buildUserScopedKey(token, "alert-center");
}

export function buildMyWorkspaceQueryKey(token: string) {
  return buildUserScopedKey(token, "workspace");
}

export function getMyWorkspaceQueryOptions(cacheKey: string): ApiQueryOptions {
  return buildPersistedQueryOptions(cacheKey, "workspace", TWO_MINUTES_MS, TEN_MINUTES_MS);
}

export function getUserScopedQueryOptions(label: string): ApiQueryOptions {
  return {
    staleTimeMs: TWO_MINUTES_MS,  // 30秒 -> 2分钟
    cacheTimeMs: TEN_MINUTES_MS,  // 5分钟 -> 10分钟
    label,
  };
}

export function buildStockOverviewQueryKey(symbol: string) {
  return `stock:overview:${String(symbol || "").trim().toUpperCase()}`;
}

export function getStockOverviewQueryOptions(cacheKey: string): ApiQueryOptions {
  return buildPersistedQueryOptions(cacheKey, "stock-overview", 10_000, TWO_MINUTES_MS);
}

export function buildStockExtrasQueryKey(symbol: string) {
  return `stock:extras:${String(symbol || "").trim().toUpperCase()}`;
}

export function getStockExtrasQueryOptions(cacheKey: string): ApiQueryOptions {
  return buildPersistedQueryOptions(cacheKey, "stock-extras", THIRTY_SECONDS_MS, TWO_MINUTES_MS);
}
