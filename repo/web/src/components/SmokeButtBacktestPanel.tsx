import dynamic from "next/dynamic";
import React, { useEffect, useMemo, useState } from "react";

import {
  buildStrategyBacktestQueryKey,
  getStrategyBacktestQueryOptions,
  loadStrategyBacktest,
} from "../domain/strategyScore";
import { useApiQuery } from "../hooks/useApiQuery";
import { SmokeButtBacktestResponse } from "../services/api";
import { formatNullableNumber, formatPercent } from "../utils/format";

type Props = {
  market?: "" | "A" | "HK" | "US";
};

const SmokeButtBacktestWindows = dynamic(
  () => import("./SmokeButtBacktestWindows").then((module) => module.SmokeButtBacktestWindows),
  {
    ssr: false,
    loading: () => <div className="helper">准备回测图表...</div>,
  },
);

function formatPercentValue(value?: number | null, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return formatPercent(value, digits);
}

function confidenceCards(payload: SmokeButtBacktestResponse) {
  if (!payload) {
    return [];
  }
  return [
    {
      label: "验证 Rank IC",
      value: payload.confidence.validation_rank_ic,
      render: (value?: number | null) => formatNullableNumber(value, 3),
      helper: "验证集排序相关性",
    },
    {
      label: "20日分层利差",
      value: payload.confidence.spread_return_20d,
      render: (value?: number | null) => formatPercentValue(value, 2),
      helper: `周期 ${payload.confidence.period_count_20d}`,
    },
    {
      label: "60日分层利差",
      value: payload.confidence.spread_return_60d,
      render: (value?: number | null) => formatPercentValue(value, 2),
      helper: `周期 ${payload.confidence.period_count_60d}`,
    },
    {
      label: "20日单调性",
      value: payload.confidence.monotonicity_20d,
      render: (value?: number | null) => formatPercentValue(value, 0),
      helper: `样本 ${payload.confidence.sample_count_20d}`,
    },
    {
      label: "60日单调性",
      value: payload.confidence.monotonicity_60d,
      render: (value?: number | null) => formatPercentValue(value, 0),
      helper: `样本 ${payload.confidence.sample_count_60d}`,
    },
    {
      label: "Top组胜率 20日",
      value: payload.confidence.top_bucket_win_rate_20d,
      render: (value?: number | null) => formatPercentValue(value, 0),
      helper: "最高评分组命中率",
    },
  ];
}

export function SmokeButtBacktestPanel({ market = "" }: Props) {
  const [shouldRenderWindows, setShouldRenderWindows] = useState(false);
  const backtestQuery = useApiQuery<SmokeButtBacktestResponse>(
    buildStrategyBacktestQueryKey(market),
    () => loadStrategyBacktest(market),
    getStrategyBacktestQueryOptions(market, "strategy-score-backtest"),
  );

  const payload = backtestQuery.data ?? null;
  const cards = useMemo(() => confidenceCards(payload), [payload]);

  useEffect(() => {
    if (!payload || typeof window === "undefined") {
      setShouldRenderWindows(false);
      return;
    }

    setShouldRenderWindows(false);

    let timeoutId: number | null = null;
    let idleId: number | null = null;
    const showWindows = () => setShouldRenderWindows(true);
    const windowWithIdle = window as Window & {
      requestIdleCallback?: (
        callback: IdleRequestCallback,
        options?: IdleRequestOptions,
      ) => number;
      cancelIdleCallback?: (handle: number) => void;
    };

    if (typeof windowWithIdle.requestIdleCallback === "function") {
      idleId = windowWithIdle.requestIdleCallback(() => showWindows(), { timeout: 600 });
    } else {
      timeoutId = window.setTimeout(showWindows, 180);
    }

    return () => {
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
      if (idleId !== null && typeof windowWithIdle.cancelIdleCallback === "function") {
        windowWithIdle.cancelIdleCallback(idleId);
      }
    };
  }, [payload]);

  if (backtestQuery.isLoading) {
    return <div className="helper">策略回测看板加载中...</div>;
  }

  if (backtestQuery.error) {
    return <div className="helper">{`策略回测加载失败：${backtestQuery.error.message}`}</div>;
  }

  if (!payload) {
    return (
      <div className="surface-empty">
        <strong>暂时没有回测数据</strong>
        <div className="helper">请先完成一次策略训练，系统会基于最新模型生成 20/60 交易日分组复盘。</div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div className="hero-grid">
        {cards.map((card) => (
          <div key={card.label} className="summary-card">
            <div className="card-title">{card.label}</div>
            <div className="stock-score-value">{card.render(card.value)}</div>
            <div className="helper">{card.helper}</div>
          </div>
        ))}
      </div>

      {shouldRenderWindows ? (
        <SmokeButtBacktestWindows payload={payload} />
      ) : (
        <div className="card surface-panel helper">
          回测摘要已就绪。详细曲线和分组表正在后台加载。
        </div>
      )}
    </div>
  );
}
