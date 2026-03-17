import React, { useEffect, useMemo, useState } from "react";

import ReactECharts from "echarts-for-react";

import { INDEX_NAME_MAP } from "../constants/indices";
import { getIndexKline, getStockKline } from "../services/api";
import { BoughtTarget } from "../utils/boughtTargets";
import { formatPercent } from "../utils/format";

type KlinePoint = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

type KlineSeries = {
  symbol: string;
  period: string;
  items: KlinePoint[];
};

type KlinePeriod = "day" | "month" | "year";

type WatchCompareState = {
  benchmarkSymbol: string;
  labels: string[];
  avgKlineAligned: Array<KlinePoint | null>;
  benchmarkCloseAligned: Array<number | null>;
  watchReturnSeries: Array<number | null>;
  benchmarkReturnSeries: Array<number | null>;
  watchLatestReturn: number | null;
  benchmarkLatestReturn: number | null;
};

type BoughtCompareState = {
  benchmarkSymbol: string;
  labels: string[];
  weightedKlineAligned: Array<KlinePoint | null>;
  benchmarkCloseAligned: Array<number | null>;
  portfolioReturnSeries: Array<number | null>;
  benchmarkReturnSeries: Array<number | null>;
  portfolioLatestReturn: number | null;
  benchmarkLatestReturn: number | null;
};

const PERIOD_OPTIONS: Array<{ value: KlinePeriod; label: string }> = [
  { value: "day", label: "日K" },
  { value: "month", label: "月K" },
  { value: "year", label: "年K" },
];

function getKlineLimit(period: KlinePeriod) {
  if (period === "year") {
    return 120;
  }
  if (period === "month") {
    return 360;
  }
  return 500;
}

function normalizeSymbol(value: string) {
  return (value || "").trim().toUpperCase();
}

function toDateKey(raw: string) {
  return String(raw || "").slice(0, 10);
}

function inferMarketFromSymbol(symbol: string): "A" | "HK" {
  const upper = normalizeSymbol(symbol);
  if (upper.startsWith("HK") || upper.endsWith(".HK")) {
    return "HK";
  }
  return "A";
}

function benchmarkSymbolByMarket(market: "A" | "HK") {
  return market === "HK" ? "HKHSI" : "000001.SH";
}

function sharesPerLotBySymbol(symbol: string) {
  return inferMarketFromSymbol(symbol) === "A" ? 100 : 1;
}

function findLastNumber(values: Array<number | null>): number | null {
  for (let index = values.length - 1; index >= 0; index -= 1) {
    const current = values[index];
    if (typeof current === "number" && Number.isFinite(current)) {
      return current;
    }
  }
  return null;
}

function buildCloseAlignWithCarry(labels: string[], closeMap: Map<string, number>) {
  let last: number | null = null;
  return labels.map((date) => {
    const value = closeMap.get(date);
    if (typeof value === "number" && Number.isFinite(value)) {
      last = value;
      return value;
    }
    return last;
  });
}

function buildPairedReturns(primarySeries: Array<number | null>, benchmarkSeries: Array<number | null>) {
  const primaryReturns: Array<number | null> = new Array(primarySeries.length).fill(null);
  const benchmarkReturns: Array<number | null> = new Array(primarySeries.length).fill(null);
  let startIndex = -1;
  for (let index = 0; index < primarySeries.length; index += 1) {
    if (
      typeof primarySeries[index] === "number" &&
      (primarySeries[index] || 0) > 0 &&
      typeof benchmarkSeries[index] === "number" &&
      (benchmarkSeries[index] || 0) > 0
    ) {
      startIndex = index;
      break;
    }
  }
  if (startIndex < 0) {
    return { primaryReturns, benchmarkReturns };
  }
  const primaryBase = primarySeries[startIndex] as number;
  const benchmarkBase = benchmarkSeries[startIndex] as number;
  for (let index = startIndex; index < primarySeries.length; index += 1) {
    const primaryValue = primarySeries[index];
    const benchmarkValue = benchmarkSeries[index];
    if (typeof primaryValue === "number" && primaryValue > 0) {
      primaryReturns[index] = primaryValue / primaryBase - 1;
    }
    if (typeof benchmarkValue === "number" && benchmarkValue > 0) {
      benchmarkReturns[index] = benchmarkValue / benchmarkBase - 1;
    }
  }
  return { primaryReturns, benchmarkReturns };
}

function formatLabel(value: string, period: KlinePeriod) {
  if (period === "year") {
    return value.slice(0, 4);
  }
  if (period === "month") {
    return value.slice(0, 7);
  }
  return value.slice(5);
}

function normalizeKlineItems(rawItems: any[]): KlinePoint[] {
  const result: KlinePoint[] = [];
  for (const raw of rawItems || []) {
    const date = toDateKey(String(raw?.date || ""));
    const open = Number(raw?.open);
    const high = Number(raw?.high);
    const low = Number(raw?.low);
    const close = Number(raw?.close);
    if (!date || !Number.isFinite(open) || !Number.isFinite(high) || !Number.isFinite(low) || !Number.isFinite(close)) {
      continue;
    }
    result.push({ date, open, high, low, close });
  }
  result.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  return result;
}

function dedupeSymbols(values: string[]) {
  const unique = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const symbol = normalizeSymbol(value);
    if (!symbol || unique.has(symbol)) {
      continue;
    }
    unique.add(symbol);
    result.push(symbol);
  }
  return result;
}

function buildAlignedPointSeries(
  labels: string[],
  items: KlinePoint[],
  options?: { startDate?: string; defaultClose?: number },
) {
  const itemMap = new Map(items.map((item) => [item.date, item]));
  let lastClose: number | null = null;
  return labels.map((date) => {
    if (options?.startDate && date < options.startDate) {
      return null;
    }
    const current = itemMap.get(date);
    if (current) {
      lastClose = current.close;
      return current;
    }
    if (typeof lastClose === "number" && lastClose > 0) {
      return { date, open: lastClose, high: lastClose, low: lastClose, close: lastClose };
    }
    if (typeof options?.defaultClose === "number" && options.defaultClose > 0) {
      lastClose = options.defaultClose;
      return {
        date,
        open: options.defaultClose,
        high: options.defaultClose,
        low: options.defaultClose,
        close: options.defaultClose,
      };
    }
    return null;
  });
}

function averagePointSeries(labels: string[], seriesList: Array<Array<KlinePoint | null>>) {
  return labels.map((date, idx) => {
    let open = 0;
    let high = 0;
    let low = 0;
    let close = 0;
    let count = 0;
    for (const series of seriesList) {
      const point = series[idx];
      if (!point) {
        continue;
      }
      open += point.open;
      high += point.high;
      low += point.low;
      close += point.close;
      count += 1;
    }
    if (count <= 0) {
      return null;
    }
    return {
      date,
      open: open / count,
      high: high / count,
      low: low / count,
      close: close / count,
    };
  });
}

function weightedAveragePointSeries(labels: string[], seriesList: Array<Array<KlinePoint | null>>, weights: number[]) {
  return labels.map((date, idx) => {
    let open = 0;
    let high = 0;
    let low = 0;
    let close = 0;
    let weightSum = 0;
    for (let seriesIndex = 0; seriesIndex < seriesList.length; seriesIndex += 1) {
      const point = seriesList[seriesIndex][idx];
      const weight = weights[seriesIndex] || 0;
      if (!point || weight <= 0) {
        continue;
      }
      open += point.open * weight;
      high += point.high * weight;
      low += point.low * weight;
      close += point.close * weight;
      weightSum += weight;
    }
    if (weightSum <= 0) {
      return null;
    }
    return {
      date,
      open: open / weightSum,
      high: high / weightSum,
      low: low / weightSum,
      close: close / weightSum,
    };
  });
}

export function PerformanceComparisonPanel({
  watchSymbols,
  boughtTargets,
}: {
  watchSymbols: string[];
  boughtTargets: BoughtTarget[];
}) {
  const [period, setPeriod] = useState<KlinePeriod>("day");

  const [watchLoading, setWatchLoading] = useState(false);
  const [watchError, setWatchError] = useState<string | null>(null);
  const [watchState, setWatchState] = useState<WatchCompareState | null>(null);

  const [boughtLoading, setBoughtLoading] = useState(false);
  const [boughtError, setBoughtError] = useState<string | null>(null);
  const [boughtState, setBoughtState] = useState<BoughtCompareState | null>(null);

  useEffect(() => {
    const symbols = dedupeSymbols(watchSymbols || []);
    if (symbols.length === 0) {
      setWatchState(null);
      setWatchLoading(false);
      setWatchError(null);
      return;
    }
    const hkCount = symbols.filter((item) => inferMarketFromSymbol(item) === "HK").length;
    const market: "A" | "HK" = hkCount > symbols.length / 2 ? "HK" : "A";
    const benchmarkSymbol = benchmarkSymbolByMarket(market);
    const limit = getKlineLimit(period);

    let active = true;
    setWatchLoading(true);
    setWatchError(null);

    Promise.all([
      getIndexKline(benchmarkSymbol, { period, limit }),
      Promise.allSettled(symbols.map((item) => getStockKline(item, { period, limit }))),
    ])
      .then(([benchRes, stockResults]) => {
        if (!active) {
          return;
        }
        const benchmarkItems = normalizeKlineItems((benchRes as KlineSeries).items || []);
        if (benchmarkItems.length === 0) {
          setWatchState(null);
          setWatchError("观察组合或大盘K线数据不足");
          return;
        }

        const labels = benchmarkItems.map((item) => item.date);
        const benchmarkCloseMap = new Map(benchmarkItems.map((item) => [item.date, item.close]));
        const benchmarkCloseAligned = buildCloseAlignWithCarry(labels, benchmarkCloseMap);

        const pointSeriesList: Array<Array<KlinePoint | null>> = [];
        stockResults.forEach((result) => {
          if (result.status !== "fulfilled") {
            return;
          }
          const items = normalizeKlineItems(((result.value as KlineSeries).items || []) as any[]);
          if (items.length === 0) {
            return;
          }
          pointSeriesList.push(buildAlignedPointSeries(labels, items));
        });

        if (pointSeriesList.length === 0) {
          setWatchState(null);
          setWatchError("观察组合K线数据不足");
          return;
        }

        const avgKlineAligned = averagePointSeries(labels, pointSeriesList);
        const watchCloseSeries = avgKlineAligned.map((item) => item?.close ?? null);
        const { primaryReturns, benchmarkReturns } = buildPairedReturns(watchCloseSeries, benchmarkCloseAligned);

        setWatchState({
          benchmarkSymbol,
          labels,
          avgKlineAligned,
          benchmarkCloseAligned,
          watchReturnSeries: primaryReturns,
          benchmarkReturnSeries: benchmarkReturns,
          watchLatestReturn: findLastNumber(primaryReturns),
          benchmarkLatestReturn: findLastNumber(benchmarkReturns),
        });
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setWatchState(null);
        setWatchError(err.message || "观察组合收益对比加载失败");
      })
      .finally(() => {
        if (active) {
          setWatchLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [period, watchSymbols]);

  useEffect(() => {
    if (boughtTargets.length === 0) {
      setBoughtState(null);
      setBoughtLoading(false);
      setBoughtError(null);
      return;
    }
    const normalizedTargets = boughtTargets
      .map((item) => ({
        ...item,
        symbol: normalizeSymbol(item.symbol),
        buyDate: toDateKey(item.buyDate),
      }))
      .filter((item) => item.symbol && item.buyDate);
    if (normalizedTargets.length === 0) {
      setBoughtState(null);
      setBoughtLoading(false);
      setBoughtError("已买标的为空");
      return;
    }

    const hkCount = normalizedTargets.filter((item) => inferMarketFromSymbol(item.symbol) === "HK").length;
    const market: "A" | "HK" = hkCount > normalizedTargets.length / 2 ? "HK" : "A";
    const benchmarkSymbol = benchmarkSymbolByMarket(market);
    const startDate = normalizedTargets
      .map((item) => item.buyDate)
      .sort((a, b) => new Date(a).getTime() - new Date(b).getTime())[0];
    const limit = getKlineLimit(period);

    let active = true;
    setBoughtLoading(true);
    setBoughtError(null);

    Promise.all([
      getIndexKline(benchmarkSymbol, { period, start: startDate, limit }),
      Promise.allSettled(
        normalizedTargets.map((item) =>
          getStockKline(item.symbol, { period, start: item.buyDate, limit }),
        ),
      ),
    ])
      .then(([benchRes, stockResults]) => {
        if (!active) {
          return;
        }
        const benchmarkItems = normalizeKlineItems((benchRes as KlineSeries).items || []);
        if (benchmarkItems.length === 0) {
          setBoughtState(null);
          setBoughtError("大盘K线数据不足");
          return;
        }

        const labels = benchmarkItems.map((item) => item.date);
        const benchmarkCloseMap = new Map(benchmarkItems.map((item) => [item.date, item.close]));
        const benchmarkCloseAligned = buildCloseAlignWithCarry(labels, benchmarkCloseMap);

        const perHoldingPointSeries: Array<Array<KlinePoint | null>> = [];
        const perHoldingCloseSeries: Array<Array<number | null>> = [];
        const holdingWeights: number[] = [];

        normalizedTargets.forEach((target, index) => {
          const stockResult = stockResults[index];
          const shareCount = target.lots * sharesPerLotBySymbol(target.symbol);
          const weight = target.buyPrice * shareCount;
          holdingWeights.push(weight > 0 ? weight : 0);

          if (stockResult.status !== "fulfilled") {
            perHoldingPointSeries.push(new Array(labels.length).fill(null));
            perHoldingCloseSeries.push(new Array(labels.length).fill(null));
            return;
          }
          const stockItems = normalizeKlineItems(((stockResult.value as KlineSeries).items || []) as any[]);
          const alignedPoints = buildAlignedPointSeries(labels, stockItems, {
            startDate: target.buyDate,
            defaultClose: target.buyPrice,
          });
          perHoldingPointSeries.push(alignedPoints);
          perHoldingCloseSeries.push(alignedPoints.map((item) => item?.close ?? null));
        });

        const weightedKlineAligned = weightedAveragePointSeries(labels, perHoldingPointSeries, holdingWeights);

        const portfolioValueSeries: Array<number | null> = [];
        const portfolioCostSeries: Array<number | null> = [];
        labels.forEach((date, idx) => {
          let value = 0;
          let cost = 0;
          let hasValue = false;
          normalizedTargets.forEach((target, targetIndex) => {
            if (date < target.buyDate) {
              return;
            }
            const shareCount = target.lots * sharesPerLotBySymbol(target.symbol);
            cost += target.buyPrice * shareCount + target.fee;
            const close = perHoldingCloseSeries[targetIndex][idx];
            if (typeof close === "number" && close > 0) {
              value += close * shareCount;
              hasValue = true;
            }
          });
          portfolioCostSeries.push(cost > 0 ? cost : null);
          portfolioValueSeries.push(hasValue ? value : null);
        });

        const portfolioReturnSeries = portfolioValueSeries.map((value, idx) => {
          const cost = portfolioCostSeries[idx];
          if (typeof value !== "number" || typeof cost !== "number" || cost <= 0) {
            return null;
          }
          return value / cost - 1;
        });

        let benchmarkStart: number | null = null;
        const benchmarkReturnSeries = benchmarkCloseAligned.map((value, idx) => {
          const portfolioRet = portfolioReturnSeries[idx];
          if (benchmarkStart === null) {
            if (typeof portfolioRet === "number" && typeof value === "number" && value > 0) {
              benchmarkStart = value;
              return 0;
            }
            return null;
          }
          if (typeof value !== "number" || value <= 0) {
            return null;
          }
          return value / benchmarkStart - 1;
        });

        setBoughtState({
          benchmarkSymbol,
          labels,
          weightedKlineAligned,
          benchmarkCloseAligned,
          portfolioReturnSeries,
          benchmarkReturnSeries,
          portfolioLatestReturn: findLastNumber(portfolioReturnSeries),
          benchmarkLatestReturn: findLastNumber(benchmarkReturnSeries),
        });
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setBoughtState(null);
        setBoughtError(err.message || "已买组合收益对比加载失败");
      })
      .finally(() => {
        if (active) {
          setBoughtLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [boughtTargets, period]);

  const watchKlineCompareOption = useMemo(() => {
    if (!watchState) {
      return null;
    }
    return {
      animation: false,
      tooltip: { trigger: "axis" },
      legend: { top: 0, data: ["观察组合K线均值", "大盘收盘"] },
      grid: { left: 48, right: 52, top: 36, bottom: 40 },
      xAxis: {
        type: "category",
        data: watchState.labels.map((item) => formatLabel(item, period)),
        boundaryGap: true,
      },
      yAxis: [{ type: "value", scale: true }, { type: "value", scale: true }],
      series: [
        {
          name: "观察组合K线均值",
          type: "candlestick",
          data: watchState.avgKlineAligned.map((item) => (item ? [item.open, item.close, item.low, item.high] : "-")),
          itemStyle: {
            color: "#ef4444",
            color0: "#10b981",
            borderColor: "#ef4444",
            borderColor0: "#10b981",
          },
        },
        {
          name: "大盘收盘",
          type: "line",
          yAxisIndex: 1,
          smooth: true,
          showSymbol: false,
          data: watchState.benchmarkCloseAligned,
          lineStyle: { width: 1.8, color: "#2563eb" },
        },
      ],
    };
  }, [period, watchState]);

  const watchReturnOption = useMemo(() => {
    if (!watchState) {
      return null;
    }
    return {
      animation: false,
      tooltip: { trigger: "axis" },
      legend: { top: 0, data: ["观察组合收益率", "大盘收益率"] },
      grid: { left: 48, right: 24, top: 36, bottom: 40 },
      xAxis: {
        type: "category",
        data: watchState.labels.map((item) => formatLabel(item, period)),
      },
      yAxis: { type: "value", axisLabel: { formatter: (val: number) => `${(val * 100).toFixed(0)}%` } },
      series: [
        {
          name: "观察组合收益率",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: watchState.watchReturnSeries,
          lineStyle: { width: 2, color: "#ef4444" },
        },
        {
          name: "大盘收益率",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: watchState.benchmarkReturnSeries,
          lineStyle: { width: 2, color: "#2563eb" },
        },
      ],
    };
  }, [period, watchState]);

  const boughtKlineCompareOption = useMemo(() => {
    if (!boughtState) {
      return null;
    }
    return {
      animation: false,
      tooltip: { trigger: "axis" },
      legend: { top: 0, data: ["已买组合K线加权均值", "大盘收盘"] },
      grid: { left: 48, right: 52, top: 36, bottom: 40 },
      xAxis: {
        type: "category",
        data: boughtState.labels.map((item) => formatLabel(item, period)),
        boundaryGap: true,
      },
      yAxis: [{ type: "value", scale: true }, { type: "value", scale: true }],
      series: [
        {
          name: "已买组合K线加权均值",
          type: "candlestick",
          data: boughtState.weightedKlineAligned.map((item) => (item ? [item.open, item.close, item.low, item.high] : "-")),
          itemStyle: {
            color: "#ef4444",
            color0: "#10b981",
            borderColor: "#ef4444",
            borderColor0: "#10b981",
          },
        },
        {
          name: "大盘收盘",
          type: "line",
          yAxisIndex: 1,
          smooth: true,
          showSymbol: false,
          data: boughtState.benchmarkCloseAligned,
          lineStyle: { width: 1.8, color: "#2563eb" },
        },
      ],
    };
  }, [boughtState, period]);

  const boughtReturnOption = useMemo(() => {
    if (!boughtState) {
      return null;
    }
    return {
      animation: false,
      tooltip: { trigger: "axis" },
      legend: { top: 0, data: ["已买组合收益率", "大盘收益率"] },
      grid: { left: 48, right: 24, top: 36, bottom: 40 },
      xAxis: {
        type: "category",
        data: boughtState.labels.map((item) => formatLabel(item, period)),
      },
      yAxis: { type: "value", axisLabel: { formatter: (val: number) => `${(val * 100).toFixed(0)}%` } },
      series: [
        {
          name: "已买组合收益率",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: boughtState.portfolioReturnSeries,
          lineStyle: { width: 2, color: "#d97706" },
        },
        {
          name: "大盘收益率",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: boughtState.benchmarkReturnSeries,
          lineStyle: { width: 2, color: "#2563eb" },
        },
      ],
    };
  }, [boughtState, period]);

  const periodLabel = PERIOD_OPTIONS.find((item) => item.value === period)?.label || "日K";

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div className="toolbar" style={{ marginBottom: 4 }}>
        <span className="helper">K线周期</span>
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

      <section className="card">
        <div className="card-title">{`观察组合收益对比（K线均值 · ${periodLabel}）`}</div>
        {watchSymbols.length === 0 ? <div className="helper">暂无观察标的，先添加后再查看组合图。</div> : null}
        {watchLoading ? <div className="helper">观察组合收益图加载中...</div> : null}
        {!watchLoading && watchError ? <div className="helper">{`加载失败：${watchError}`}</div> : null}
        {!watchLoading && !watchError && watchState ? (
          <>
            <div className="helper" style={{ marginBottom: 10 }}>
              {`观察组合收益率${
                watchState.watchLatestReturn === null ? "--" : formatPercent(watchState.watchLatestReturn)
              } · ${INDEX_NAME_MAP[watchState.benchmarkSymbol] || watchState.benchmarkSymbol}收益率${
                watchState.benchmarkLatestReturn === null ? "--" : formatPercent(watchState.benchmarkLatestReturn)
              }`}
            </div>
            <div className="grid grid-3">
              <div className="card">
                {watchKlineCompareOption ? <ReactECharts option={watchKlineCompareOption} style={{ height: 300 }} /> : null}
              </div>
              <div className="card">
                {watchReturnOption ? <ReactECharts option={watchReturnOption} style={{ height: 300 }} /> : null}
              </div>
            </div>
          </>
        ) : null}
      </section>

      <section className="card">
        <div className="card-title">{`已买组合收益对比（持仓金额加权K线 · ${periodLabel}）`}</div>
        {boughtTargets.length === 0 ? <div className="helper">暂无已买标的，先在上方加入已买标的。</div> : null}
        {boughtLoading ? <div className="helper">已买组合收益图加载中...</div> : null}
        {!boughtLoading && boughtError ? <div className="helper">{`加载失败：${boughtError}`}</div> : null}
        {!boughtLoading && !boughtError && boughtState ? (
          <>
            <div className="helper" style={{ marginBottom: 10 }}>
              {`已买组合收益率${
                boughtState.portfolioLatestReturn === null ? "--" : formatPercent(boughtState.portfolioLatestReturn)
              } · ${INDEX_NAME_MAP[boughtState.benchmarkSymbol] || boughtState.benchmarkSymbol}收益率${
                boughtState.benchmarkLatestReturn === null ? "--" : formatPercent(boughtState.benchmarkLatestReturn)
              }`}
            </div>
            <div className="grid grid-3">
              <div className="card">
                {boughtKlineCompareOption ? <ReactECharts option={boughtKlineCompareOption} style={{ height: 300 }} /> : null}
              </div>
              <div className="card">
                {boughtReturnOption ? <ReactECharts option={boughtReturnOption} style={{ height: 300 }} /> : null}
              </div>
            </div>
          </>
        ) : null}
      </section>
    </div>
  );
}
