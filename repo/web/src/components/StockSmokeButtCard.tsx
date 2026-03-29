import Link from "next/link";
import React, { useMemo } from "react";

import {
  buildStrategyDetailQueryKey,
  buildStrategySignalExplanation,
  getStrategyScoreQueryOptions,
  loadStrategyDetail,
  normalizeStrategySymbol,
} from "../domain/strategyScore";
import { useApiQuery } from "../hooks/useApiQuery";
import { SmokeButtDetailResponse } from "../services/api";
import { formatNullableNumber, formatPercent } from "../utils/format";

type Props = {
  symbol: string;
};

const SIGNAL_LABELS: Record<string, string> = {
  strong_buy: "Strong Buy",
  buy: "Buy",
  watch: "Watch",
  avoid: "Avoid",
};

function signalTone(signal?: string | null) {
  if (signal === "strong_buy" || signal === "buy") {
    return "positive";
  }
  if (signal === "avoid") {
    return "negative";
  }
  return "neutral";
}

export function StockSmokeButtCard({ symbol }: Props) {
  const normalizedSymbol = useMemo(() => normalizeStrategySymbol(symbol), [symbol]);
  const detailQuery = useApiQuery<SmokeButtDetailResponse>(
    normalizedSymbol ? buildStrategyDetailQueryKey(normalizedSymbol) : null,
    () => loadStrategyDetail(normalizedSymbol),
    getStrategyScoreQueryOptions("strategy-score-detail"),
  );

  if (!normalizedSymbol) {
    return null;
  }

  if (detailQuery.isLoading) {
    return <div className="card helper">AutoGluon smoke-butt signal is loading...</div>;
  }

  if (detailQuery.error && !detailQuery.data) {
    return <div className="card helper">AutoGluon smoke-butt signal is temporarily unavailable.</div>;
  }

  if (!detailQuery.data) {
    return (
      <div className="card strategy-card">
        <div className="card-title">AutoGluon Smoke Butt Strategy</div>
        <div className="helper">
          No strategy output is available yet. Run a training pass on the strategy page, then return here to inspect
          the stock-level score.
        </div>
        <div style={{ marginTop: 14 }}>
          <Link href="/strategy/smoke-butt" className="badge-link">
            Open strategy page
          </Link>
        </div>
      </div>
    );
  }

  const detail = detailQuery.data;
  const expectedReturn = detail.expected_return ?? null;
  const signal = SIGNAL_LABELS[detail.signal] ?? detail.signal;

  return (
    <div className="card strategy-card">
      <div className="stock-profile-header">
        <div>
          <div className="card-title">AutoGluon Smoke Butt Strategy</div>
          <div className="helper">
            Model as of {detail.run.as_of} | training rows {detail.run.train_rows} | scored symbols {detail.run.scored_rows}
          </div>
        </div>
        <div className="strategy-score-hero">
          <div className="stock-score-value">{formatNullableNumber(detail.score, 1)}</div>
          <div className="helper">Strategy score</div>
        </div>
      </div>

      <div className="strategy-summary-grid">
        <div className="summary-card">
          <div className="helper">Expected return</div>
          <div className="metric-value">{expectedReturn !== null ? formatPercent(expectedReturn, 2) : "--"}</div>
          <div className="metric-helper">Next {detail.run.label_horizon} trading days</div>
        </div>
        <div className="summary-card">
          <div className="helper">Current rank</div>
          <div className="metric-value">#{detail.rank}</div>
          <div className="metric-helper">Ahead of {formatPercent(detail.percentile, 0)} of scored names</div>
        </div>
        <div className="summary-card">
          <div className="helper">Signal</div>
          <div className="strategy-pill strategy-pill-large" data-tone={signalTone(detail.signal)}>
            {signal}
          </div>
          <div className="metric-helper">
            Trained at {new Date(detail.run.trained_at).toLocaleString("zh-CN")}
          </div>
        </div>
      </div>

      <div className="stock-summary">{buildStrategySignalExplanation(detail)}</div>
      <div className="helper" style={{ marginTop: 8 }}>
        {detail.summary ?? "No strategy summary is available yet."}
      </div>

      <div className="strategy-pill-row">
        {detail.drivers.map((driver) => (
          <span key={`${driver.label}-${driver.display_value ?? ""}`} className="strategy-pill" data-tone={driver.tone}>
            {driver.label}
            {driver.display_value ? ` | ${driver.display_value}` : ""}
          </span>
        ))}
      </div>

      <div className="strategy-feature-grid">
        {detail.feature_values.map((item) => (
          <div key={item.name} className="strategy-feature-card">
            <div className="helper">{item.name}</div>
            <div className="metric-value">{item.display_value ?? "--"}</div>
          </div>
        ))}
      </div>

      {!!detail.run.feature_importance.length && (
        <div style={{ marginTop: 18 }}>
          <div className="card-title">Top features in the latest model run</div>
          <div className="strategy-pill-row">
            {detail.run.feature_importance.slice(0, 4).map((item) => (
              <span key={item.feature} className="strategy-pill" data-tone="neutral">
                {item.feature}
                {item.importance !== null && item.importance !== undefined ? ` | ${formatNullableNumber(item.importance, 2)}` : ""}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
