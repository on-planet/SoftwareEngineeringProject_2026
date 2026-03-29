import { ApiPage, ApiQueryOptions, request, requestJson } from "./core";

export type StrategySignal = "strong_buy" | "buy" | "watch" | "avoid";

export type SmokeButtFeatureImportance = {
  feature: string;
  importance?: number | null;
  stddev?: number | null;
  p_value?: number | null;
  n?: number | null;
};

export type SmokeButtLeaderboardItem = {
  model: string;
  score_val?: number | null;
  fit_time?: number | null;
  pred_time_val?: number | null;
};

export type SmokeButtRun = {
  id: number;
  strategy_code: string;
  strategy_name: string;
  as_of: string;
  label_horizon: number;
  status: string;
  model_path?: string | null;
  train_rows: number;
  scored_rows: number;
  trained_at: string;
  evaluation: Record<string, number | string | null>;
  leaderboard: SmokeButtLeaderboardItem[];
  feature_importance: SmokeButtFeatureImportance[];
};

export type SmokeButtCandidate = {
  symbol: string;
  name: string;
  market: string;
  sector: string;
  as_of: string;
  score: number;
  rank: number;
  percentile: number;
  expected_return?: number | null;
  signal: StrategySignal;
  summary?: string | null;
  signal_explanation?: string | null;
};

export type SmokeButtDriver = {
  label: string;
  tone: string;
  value?: number | null;
  display_value?: string | null;
};

export type SmokeButtFeatureValue = {
  name: string;
  value?: number | null;
  display_value?: string | null;
};

export type SmokeButtDetailResponse =
  | (SmokeButtCandidate & {
      run: SmokeButtRun;
      drivers: SmokeButtDriver[];
      feature_values: SmokeButtFeatureValue[];
    })
  | null;

export type SmokeButtListResponse = ApiPage<SmokeButtCandidate> & {
  run?: SmokeButtRun | null;
};

export type SmokeButtBacktestCurvePoint = {
  date: string;
  period_return?: number | null;
  cumulative_return?: number | null;
};

export type SmokeButtBacktestBucket = {
  bucket: string;
  label: string;
  bucket_index: number;
  avg_return?: number | null;
  win_rate?: number | null;
  max_drawdown?: number | null;
  avg_predicted_return?: number | null;
  sample_count: number;
  period_count: number;
  curve: SmokeButtBacktestCurvePoint[];
};

export type SmokeButtBacktestWindowSummary = {
  top_bucket_return?: number | null;
  top_bucket_win_rate?: number | null;
  top_bucket_max_drawdown?: number | null;
  spread_return?: number | null;
  spread_win_rate?: number | null;
  spread_hit_rate?: number | null;
  monotonicity?: number | null;
  sample_count: number;
  period_count: number;
};

export type SmokeButtBacktestWindow = {
  horizon_days: number;
  rebalance_step: number;
  buckets: SmokeButtBacktestBucket[];
  summary: SmokeButtBacktestWindowSummary;
};

export type SmokeButtBacktestConfidence = {
  validation_rank_ic?: number | null;
  validation_mae?: number | null;
  validation_rmse?: number | null;
  spread_return_20d?: number | null;
  spread_return_60d?: number | null;
  monotonicity_20d?: number | null;
  monotonicity_60d?: number | null;
  top_bucket_win_rate_20d?: number | null;
  top_bucket_win_rate_60d?: number | null;
  period_count_20d: number;
  period_count_60d: number;
  sample_count_20d: number;
  sample_count_60d: number;
};

export type SmokeButtBacktestResponse = {
  run: SmokeButtRun;
  market?: "A" | "HK" | "US" | null;
  bucket_count: number;
  windows: SmokeButtBacktestWindow[];
  confidence: SmokeButtBacktestConfidence;
} | null;

export async function getSmokeButtStrategyLeaderboard(
  params?: {
    market?: "A" | "HK" | "US";
    signal?: StrategySignal;
    limit?: number;
    offset?: number;
  },
  options?: ApiQueryOptions,
) {
  const query = new URLSearchParams();
  if (params?.market) query.set("market", params.market);
  if (params?.signal) query.set("signal", params.signal);
  if (params?.limit !== undefined) query.set("limit", String(params.limit));
  if (params?.offset !== undefined) query.set("offset", String(params.offset));
  const suffix = query.toString();
  return request<SmokeButtListResponse>(`/api/strategy/smoke-butt${suffix ? `?${suffix}` : ""}`, {
    ...options,
    label: options?.label ?? "strategy-score-leaderboard",
  });
}

export async function getSmokeButtStrategyDetail(symbol: string, options?: ApiQueryOptions) {
  return request<SmokeButtDetailResponse>(`/api/strategy/smoke-butt/${encodeURIComponent(symbol)}`, {
    ...options,
    label: options?.label ?? "strategy-score-detail",
  });
}

export async function getSmokeButtBacktest(
  params?: {
    market?: "A" | "HK" | "US";
    bucket_count?: number;
  },
  options?: ApiQueryOptions,
) {
  const query = new URLSearchParams();
  if (params?.market) query.set("market", params.market);
  if (params?.bucket_count !== undefined) query.set("bucket_count", String(params.bucket_count));
  const suffix = query.toString();
  return request<SmokeButtBacktestResponse>(`/api/strategy/smoke-butt/backtest${suffix ? `?${suffix}` : ""}`, {
    ...options,
    label: options?.label ?? "strategy-score-backtest",
  });
}

export async function trainSmokeButtStrategy(payload?: {
  as_of?: string;
  horizon_days?: number;
  sample_step?: number;
  time_limit_seconds?: number;
  force_retrain?: boolean;
}) {
  return requestJson<{ run: SmokeButtRun; items: SmokeButtCandidate[] }>(
    "/api/strategy/smoke-butt/train",
    {
      as_of: payload?.as_of ?? null,
      horizon_days: payload?.horizon_days ?? 60,
      sample_step: payload?.sample_step ?? 21,
      time_limit_seconds: payload?.time_limit_seconds ?? 120,
      force_retrain: payload?.force_retrain ?? false,
    },
    { retry: 0, label: "strategy-score-train" },
  );
}
