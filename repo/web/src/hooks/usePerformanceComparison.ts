import { useMemo, useState } from "react";

import { useApiQuery } from "./useApiQuery";
import { getCompareKline } from "../services/api";
import { BoughtTarget } from "../utils/boughtTargets";
import {
  benchmarkSymbolByMarket,
  buildBoughtCompareState,
  buildKlineCompareOption,
  buildReturnCompareOption,
  buildWatchCompareState,
  dedupeSymbols,
  getKlineLimit,
  inferMarketFromSymbol,
  KlinePeriod,
  normalizeSymbol,
  PERIOD_OPTIONS,
  toDateKey,
} from "../components/performance/performanceUtils";
import { marketTheme } from "../styles/marketTheme";

type UsePerformanceComparisonOptions = {
  watchSymbols: string[];
  boughtTargets: BoughtTarget[];
};

export type PerformanceComparisonModel = ReturnType<typeof usePerformanceComparison>;

export function usePerformanceComparison({
  watchSymbols,
  boughtTargets,
}: UsePerformanceComparisonOptions) {
  const [period, setPeriod] = useState<KlinePeriod>("day");

  const normalizedWatchSymbols = useMemo(() => dedupeSymbols(watchSymbols || []), [watchSymbols]);
  const watchRequest = useMemo(() => {
    if (normalizedWatchSymbols.length === 0) {
      return null;
    }
    const hkCount = normalizedWatchSymbols.filter((item) => inferMarketFromSymbol(item) === "HK").length;
    const market: "A" | "HK" = hkCount > normalizedWatchSymbols.length / 2 ? "HK" : "A";
    const benchmarkSymbol = benchmarkSymbolByMarket(market);
    const limit = getKlineLimit(period);
    return {
      benchmarkSymbol,
      limit,
      series: [
        { symbol: benchmarkSymbol, kind: "index" as const },
        ...normalizedWatchSymbols.map((symbol) => ({ symbol, kind: "stock" as const })),
      ],
    };
  }, [normalizedWatchSymbols, period]);

  const normalizedBoughtTargets = useMemo(
    () =>
      boughtTargets
        .map((item) => ({
          ...item,
          symbol: normalizeSymbol(item.symbol),
          buyDate: toDateKey(item.buyDate),
        }))
        .filter((item) => item.symbol && item.buyDate),
    [boughtTargets],
  );

  const boughtRequest = useMemo(() => {
    if (normalizedBoughtTargets.length === 0) {
      return null;
    }
    const hkCount = normalizedBoughtTargets.filter((item) => inferMarketFromSymbol(item.symbol) === "HK").length;
    const market: "A" | "HK" = hkCount > normalizedBoughtTargets.length / 2 ? "HK" : "A";
    const benchmarkSymbol = benchmarkSymbolByMarket(market);
    const startDate = normalizedBoughtTargets
      .map((item) => item.buyDate)
      .sort((a, b) => new Date(a).getTime() - new Date(b).getTime())[0];
    const limit = getKlineLimit(period);
    return {
      benchmarkSymbol,
      limit,
      series: [
        { symbol: benchmarkSymbol, kind: "index" as const, start: startDate },
        ...normalizedBoughtTargets.map((item) => ({
          symbol: item.symbol,
          kind: "stock" as const,
          start: item.buyDate,
        })),
      ],
    };
  }, [normalizedBoughtTargets, period]);

  const watchQuery = useApiQuery(
    watchRequest
      ? ["compare-kline", "watch", period, watchRequest.benchmarkSymbol, ...normalizedWatchSymbols]
      : null,
    () =>
      getCompareKline({
        period,
        limit: watchRequest?.limit,
        series: watchRequest?.series || [],
      }),
  );

  const boughtQuery = useApiQuery(
    boughtRequest
      ? [
          "compare-kline",
          "bought",
          period,
          boughtRequest.benchmarkSymbol,
          ...normalizedBoughtTargets.map((item) => `${item.symbol}:${item.buyDate}`),
        ]
      : null,
    () =>
      getCompareKline({
        period,
        limit: boughtRequest?.limit,
        series: boughtRequest?.series || [],
      }),
  );

  const watchResult = useMemo(
    () => buildWatchCompareState(watchQuery.data, watchRequest?.benchmarkSymbol || ""),
    [watchQuery.data, watchRequest],
  );
  const boughtResult = useMemo(
    () => buildBoughtCompareState(boughtQuery.data, boughtRequest?.benchmarkSymbol || "", normalizedBoughtTargets),
    [boughtQuery.data, boughtRequest, normalizedBoughtTargets],
  );

  const watchState = watchResult.state;
  const watchError = watchQuery.error?.message || watchResult.error;
  const boughtState = boughtResult.state;
  const boughtError = boughtQuery.error?.message || boughtResult.error;

  const watchKlineCompareOption = useMemo(() => {
    if (!watchState) {
      return null;
    }
    return buildKlineCompareOption({
      labels: watchState.labels,
      period,
      candlestickLabel: "观察组合 K 线均值",
      candlestickSeries: watchState.avgKlineAligned,
      benchmarkLabel: "大盘收盘",
      benchmarkSeries: watchState.benchmarkCloseAligned,
    });
  }, [period, watchState]);

  const watchReturnOption = useMemo(() => {
    if (!watchState) {
      return null;
    }
    return buildReturnCompareOption({
      labels: watchState.labels,
      period,
      primaryLabel: "观察组合收益率",
      primarySeries: watchState.watchReturnSeries,
      primaryColor: marketTheme.trend.rise,
      benchmarkLabel: "大盘收益率",
      benchmarkSeries: watchState.benchmarkReturnSeries,
    });
  }, [period, watchState]);

  const boughtKlineCompareOption = useMemo(() => {
    if (!boughtState) {
      return null;
    }
    return buildKlineCompareOption({
      labels: boughtState.labels,
      period,
      candlestickLabel: "持仓组合 K 线加权均值",
      candlestickSeries: boughtState.weightedKlineAligned,
      benchmarkLabel: "大盘收盘",
      benchmarkSeries: boughtState.benchmarkCloseAligned,
    });
  }, [boughtState, period]);

  const boughtReturnOption = useMemo(() => {
    if (!boughtState) {
      return null;
    }
    return buildReturnCompareOption({
      labels: boughtState.labels,
      period,
      primaryLabel: "持仓组合收益率",
      primarySeries: boughtState.portfolioReturnSeries,
      primaryColor: marketTheme.chart.akshare,
      benchmarkLabel: "大盘收益率",
      benchmarkSeries: boughtState.benchmarkReturnSeries,
    });
  }, [boughtState, period]);

  const periodLabel = PERIOD_OPTIONS.find((item) => item.value === period)?.label || "日线";

  return {
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
  };
}
