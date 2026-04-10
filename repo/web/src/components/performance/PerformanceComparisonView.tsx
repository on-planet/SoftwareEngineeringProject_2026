import React from "react";
import ReactECharts from "echarts-for-react";

import { INDEX_NAME_MAP } from "../../constants/indices";
import { PerformanceComparisonModel } from "../../hooks/usePerformanceComparison";
import { PERIOD_OPTIONS } from "./performanceUtils";
import { formatPercent } from "../../utils/format";

import styles from "./PerformanceComparisonView.module.css";

type PerformanceComparisonViewProps = {
  model: PerformanceComparisonModel;
};

function trendClassName(value: number | null) {
  if (value === null || Number.isNaN(value)) {
    return "trend-neutral";
  }
  if (value > 0) {
    return "trend-up";
  }
  if (value < 0) {
    return "trend-down";
  }
  return "trend-neutral";
}

function QueryState({
  isLoading,
  error,
  emptyTitle,
  emptyHelper,
  children,
}: {
  isLoading: boolean;
  error: string | null;
  emptyTitle: string;
  emptyHelper: string;
  children: React.ReactNode;
}) {
  if (isLoading) {
    return (
      <div className="skeleton-stack">
        <span className="skeleton-line" data-width="medium" />
        <div className="skeleton-card" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="surface-empty">
        <strong>加载失败</strong>
        <div className="helper">{error}</div>
      </div>
    );
  }

  if (!children) {
    return (
      <div className="surface-empty">
        <strong>{emptyTitle}</strong>
        <div className="helper">{emptyHelper}</div>
      </div>
    );
  }

  return <>{children}</>;
}

export function PerformanceComparisonView({ model }: PerformanceComparisonViewProps) {
  const {
    period,
    setPeriod,
    periodLabel,
    normalizedWatchSymbols,
    normalizedBoughtTargets,
    watchQuery,
    boughtQuery,
    watchState,
    watchError,
    boughtState,
    boughtError,
    watchKlineCompareOption,
    watchReturnOption,
    boughtKlineCompareOption,
    boughtReturnOption,
  } = model;

  return (
    <div className={styles.stack}>
      <div className={`toolbar sticky-filter-bar ${styles.toolbar}`}>
        <span className="helper">K 线周期</span>
        {PERIOD_OPTIONS.map((item) => (
          <button
            key={item.value}
            type="button"
            className="stock-page-button"
            data-active={period === item.value}
            onClick={() => setPeriod(item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <section className={`card market-panel ${styles.section}`}>
        <div className="section-headline">
          <div>
            <div className="card-title">{`观察组合收益对比 · ${periodLabel}`}</div>
            <div className="helper">自选组合按等权均值对齐，大盘基准自动根据标的市场选择。</div>
          </div>
          <span className="kicker">观察</span>
        </div>

        {normalizedWatchSymbols.length === 0 ? (
          <div className="surface-empty">
            <strong>暂无观察标的</strong>
            <div className="helper">先添加观察标的后再查看组合收益和 K 线对比。</div>
          </div>
        ) : (
          <QueryState
            isLoading={watchQuery.isLoading}
            error={watchError}
            emptyTitle="暂无可展示数据"
            emptyHelper="观察组合和基准指数都需要可用 K 线后才能完成对齐。"
          >
            {watchState && watchKlineCompareOption && watchReturnOption ? (
              <>
                <div className={styles.summary}>
                  <div className={styles.summaryChip}>
                    观察组合
                    <span className={trendClassName(watchState.watchLatestReturn)}>
                      {watchState.watchLatestReturn === null ? "--" : formatPercent(watchState.watchLatestReturn)}
                    </span>
                  </div>
                  <div className={styles.summaryChip}>
                    {INDEX_NAME_MAP[watchState.benchmarkSymbol] || watchState.benchmarkSymbol}
                    <span className={trendClassName(watchState.benchmarkLatestReturn)}>
                      {watchState.benchmarkLatestReturn === null
                        ? "--"
                        : formatPercent(watchState.benchmarkLatestReturn)}
                    </span>
                  </div>
                </div>
                <div className={styles.chartGrid}>
                  <div className={`card ${styles.chartCard}`}>
                    <ReactECharts option={watchKlineCompareOption} style={{ height: 300 }} />
                  </div>
                  <div className={`card ${styles.chartCard}`}>
                    <ReactECharts option={watchReturnOption} style={{ height: 300 }} />
                  </div>
                </div>
              </>
            ) : null}
          </QueryState>
        )}
      </section>

      <section className={`card market-panel ${styles.section}`} data-tone="warm">
        <div className="section-headline">
          <div>
            <div className="card-title">{`持仓组合收益对比 · ${periodLabel}`}</div>
            <div className="helper">按持仓金额加权，组合收益从每笔买入日期开始累计。</div>
          </div>
          <span className="kicker">持仓</span>
        </div>

        {normalizedBoughtTargets.length === 0 ? (
          <div className="surface-empty">
            <strong>暂无持仓标的</strong>
            <div className="helper">先录入买入价格、手数和日期后再查看持仓组合表现。</div>
          </div>
        ) : (
          <QueryState
            isLoading={boughtQuery.isLoading}
            error={boughtError}
            emptyTitle="暂无可展示数据"
            emptyHelper="持仓组合需要基准指数与对应股票都有足够的历史行情。"
          >
            {boughtState && boughtKlineCompareOption && boughtReturnOption ? (
              <>
                <div className={styles.summary}>
                  <div className={styles.summaryChip}>
                    持仓组合
                    <span className={trendClassName(boughtState.portfolioLatestReturn)}>
                      {boughtState.portfolioLatestReturn === null
                        ? "--"
                        : formatPercent(boughtState.portfolioLatestReturn)}
                    </span>
                  </div>
                  <div className={styles.summaryChip}>
                    {INDEX_NAME_MAP[boughtState.benchmarkSymbol] || boughtState.benchmarkSymbol}
                    <span className={trendClassName(boughtState.benchmarkLatestReturn)}>
                      {boughtState.benchmarkLatestReturn === null
                        ? "--"
                        : formatPercent(boughtState.benchmarkLatestReturn)}
                    </span>
                  </div>
                </div>
                <div className={styles.chartGrid}>
                  <div className={`card ${styles.chartCard}`}>
                    <ReactECharts option={boughtKlineCompareOption} style={{ height: 300 }} />
                  </div>
                  <div className={`card ${styles.chartCard}`}>
                    <ReactECharts option={boughtReturnOption} style={{ height: 300 }} />
                  </div>
                </div>
              </>
            ) : null}
          </QueryState>
        )}
      </section>
    </div>
  );
}
