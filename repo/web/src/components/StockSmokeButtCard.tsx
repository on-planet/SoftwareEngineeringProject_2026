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
  strong_buy: "强烈买入",
  buy: "买入",
  watch: "观望",
  avoid: "回避",
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
    return <div className="card helper">AutoGluon 烟头策略信号加载中...</div>;
  }

  if (detailQuery.error && !detailQuery.data) {
    return <div className="card helper">AutoGluon 烟头策略信号暂时不可用。</div>;
  }

  if (!detailQuery.data) {
    return (
      <div className="card strategy-card">
        <div className="card-title">AutoGluon 烟头策略</div>
        <div className="helper">
          暂无策略输出。请先在策略页面运行训练，然后返回此处查看个股评分。
        </div>
        <div style={{ marginTop: 14 }}>
          <Link href="/strategy/smoke-butt" className="badge-link">
            打开策略页面
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
          <div className="card-title">AutoGluon 烟头策略</div>
          <div className="helper">
            模型日期 {detail.run.as_of} | 训练行数 {detail.run.train_rows} | 已评分标的 {detail.run.scored_rows}
          </div>
        </div>
        <div className="strategy-score-hero">
          <div className="stock-score-value">{formatNullableNumber(detail.score, 1)}</div>
          <div className="helper">策略得分</div>
        </div>
      </div>

      <div className="strategy-summary-grid">
        <div className="summary-card">
          <div className="helper">预期收益</div>
          <div className="metric-value">{expectedReturn !== null ? formatPercent(expectedReturn, 2) : "--"}</div>
          <div className="metric-helper">未来 {detail.run.label_horizon} 个交易日</div>
        </div>
        <div className="summary-card">
          <div className="helper">当前排名</div>
          <div className="metric-value">#{detail.rank}</div>
          <div className="metric-helper">领先 {formatPercent(detail.percentile, 0)} 的标的</div>
        </div>
        <div className="summary-card">
          <div className="helper">信号</div>
          <div className="strategy-pill strategy-pill-large" data-tone={signalTone(detail.signal)}>
            {signal}
          </div>
          <div className="metric-helper">
            训练于 {new Date(detail.run.trained_at).toLocaleString("zh-CN")}
          </div>
        </div>
      </div>

      <div className="stock-summary">{buildStrategySignalExplanation(detail)}</div>
      <div className="helper" style={{ marginTop: 8 }}>
        {detail.summary ?? "暂无策略摘要。"}
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
          <div className="card-title">最新模型运行的主要特征</div>
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
