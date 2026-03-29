import {
  ApiQueryOptions,
  SmokeButtBacktestResponse,
  SmokeButtCandidate,
  SmokeButtDetailResponse,
  SmokeButtListResponse,
  StrategySignal,
  getSmokeButtBacktest,
  getSmokeButtStrategyDetail,
  getSmokeButtStrategyLeaderboard,
  trainSmokeButtStrategy,
} from "../services/api";

export type StrategyScoreMarket = "" | "A" | "HK" | "US";

const STRATEGY_SCORE_STALE_TIME_MS = 2 * 60 * 1000;
const STRATEGY_SCORE_CACHE_TIME_MS = 10 * 60 * 1000;
const STRATEGY_BACKTEST_STALE_TIME_MS = 30 * 60 * 1000;
const STRATEGY_BACKTEST_CACHE_TIME_MS = 2 * 60 * 60 * 1000;

export function normalizeStrategySymbol(value: string) {
  return String(value || "").trim().toUpperCase();
}

export function buildStrategyLeaderboardQueryKey(
  market: StrategyScoreMarket,
  signal: "" | StrategySignal,
  page: number,
) {
  return ["smoke-butt-board", market || "all", signal || "all", page];
}

export function buildStrategyDetailQueryKey(symbol: string) {
  return ["smoke-butt-detail", normalizeStrategySymbol(symbol)];
}

export function buildStrategyBacktestQueryKey(market: StrategyScoreMarket) {
  return ["smoke-butt-backtest", market || "all"];
}

export function getStrategyScoreQueryOptions(label: string): ApiQueryOptions {
  return {
    staleTimeMs: STRATEGY_SCORE_STALE_TIME_MS,
    cacheTimeMs: STRATEGY_SCORE_CACHE_TIME_MS,
    retry: 1,
    label,
  };
}

export function getStrategyBacktestQueryOptions(
  market: StrategyScoreMarket,
  label = "strategy-score-backtest",
): ApiQueryOptions {
  return {
    staleTimeMs: STRATEGY_BACKTEST_STALE_TIME_MS,
    cacheTimeMs: STRATEGY_BACKTEST_CACHE_TIME_MS,
    retry: 1,
    label,
    persist: {
      key: `strategy-backtest:${market || "all"}`,
      maxAgeMs: STRATEGY_BACKTEST_CACHE_TIME_MS,
    },
  };
}

export function buildStrategySignalExplanation(item: Pick<SmokeButtCandidate, "signal" | "expected_return" | "rank" | "summary" | "signal_explanation">) {
  if (item.signal_explanation?.trim()) {
    return item.signal_explanation.trim();
  }
  const expectedReturnText =
    item.expected_return !== null && item.expected_return !== undefined
      ? `${(item.expected_return * 100).toFixed(2)}%`
      : "n/a";
  return `${item.signal} signal with model-implied return ${expectedReturnText} and rank #${item.rank}. ${item.summary || ""}`.trim();
}

export async function loadStrategyLeaderboard(
  market: StrategyScoreMarket,
  signal: "" | StrategySignal,
  limit: number,
  offset: number,
): Promise<SmokeButtListResponse> {
  return getSmokeButtStrategyLeaderboard(
    {
      market: market || undefined,
      signal: signal || undefined,
      limit,
      offset,
    },
    { cache: false, label: "strategy-score-leaderboard" },
  );
}

export async function loadStrategyDetail(symbol: string): Promise<SmokeButtDetailResponse> {
  return getSmokeButtStrategyDetail(symbol, {
    cache: false,
    label: "strategy-score-detail",
  });
}

export async function loadStrategyBacktest(market: StrategyScoreMarket): Promise<SmokeButtBacktestResponse> {
  return getSmokeButtBacktest(
    {
      market: market || undefined,
      bucket_count: 5,
    },
    {
      label: "strategy-score-backtest",
    },
  );
}

export async function retrainStrategyScore() {
  return trainSmokeButtStrategy({
    force_retrain: true,
    time_limit_seconds: 120,
  });
}
