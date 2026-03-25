import { CompareKlineResponse, CompareKlineSeriesResponse, KlinePoint } from "../../services/api";
import { BoughtTarget } from "../../utils/boughtTargets";
import { marketTheme } from "../../styles/marketTheme";

export type KlinePeriod = "day" | "month" | "year";

export type WatchCompareState = {
  benchmarkSymbol: string;
  labels: string[];
  avgKlineAligned: Array<KlinePoint | null>;
  benchmarkCloseAligned: Array<number | null>;
  watchReturnSeries: Array<number | null>;
  benchmarkReturnSeries: Array<number | null>;
  watchLatestReturn: number | null;
  benchmarkLatestReturn: number | null;
};

export type BoughtCompareState = {
  benchmarkSymbol: string;
  labels: string[];
  weightedKlineAligned: Array<KlinePoint | null>;
  benchmarkCloseAligned: Array<number | null>;
  portfolioReturnSeries: Array<number | null>;
  benchmarkReturnSeries: Array<number | null>;
  portfolioLatestReturn: number | null;
  benchmarkLatestReturn: number | null;
};

export const PERIOD_OPTIONS: Array<{ value: KlinePeriod; label: string }> = [
  { value: "day", label: "日线" },
  { value: "month", label: "月线" },
  { value: "year", label: "年线" },
];

export function getKlineLimit(period: KlinePeriod) {
  if (period === "year") {
    return 120;
  }
  if (period === "month") {
    return 360;
  }
  return 500;
}

export function normalizeSymbol(value: string) {
  return (value || "").trim().toUpperCase();
}

export function toDateKey(raw: string) {
  return String(raw || "").slice(0, 10);
}

export function inferMarketFromSymbol(symbol: string): "A" | "HK" {
  const upper = normalizeSymbol(symbol);
  if (upper.startsWith("HK") || upper.endsWith(".HK")) {
    return "HK";
  }
  return "A";
}

export function benchmarkSymbolByMarket(market: "A" | "HK") {
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

export function formatLabel(value: string, period: KlinePeriod) {
  if (period === "year") {
    return value.slice(0, 4);
  }
  if (period === "month") {
    return value.slice(0, 7);
  }
  return value.slice(5);
}

function normalizeKlineItems(rawItems: KlinePoint[]) {
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

export function dedupeSymbols(values: string[]) {
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

function buildSeriesMap(series: CompareKlineSeriesResponse[]) {
  return new Map(series.map((item) => [normalizeSymbol(item.symbol), item]));
}

export function buildWatchCompareState(
  response: CompareKlineResponse | undefined,
  benchmarkSymbol: string,
): { state: WatchCompareState | null; error: string | null } {
  if (!response) {
    return { state: null, error: null };
  }
  const seriesMap = buildSeriesMap(response.series);
  const benchmarkSeries = seriesMap.get(benchmarkSymbol);
  const benchmarkItems = normalizeKlineItems(benchmarkSeries?.items || []);
  if (benchmarkSeries?.error || benchmarkItems.length === 0) {
    return { state: null, error: "观察组合或大盘 K 线数据不足" };
  }

  const labels = benchmarkItems.map((item) => item.date);
  const benchmarkCloseMap = new Map(benchmarkItems.map((item) => [item.date, item.close]));
  const benchmarkCloseAligned = buildCloseAlignWithCarry(labels, benchmarkCloseMap);

  const pointSeriesList = response.series
    .filter((item) => item.kind === "stock" && !item.error)
    .map((item) => normalizeKlineItems(item.items || []))
    .filter((items) => items.length > 0)
    .map((items) => buildAlignedPointSeries(labels, items));

  if (pointSeriesList.length === 0) {
    return { state: null, error: "观察组合 K 线数据不足" };
  }

  const avgKlineAligned = averagePointSeries(labels, pointSeriesList);
  const watchCloseSeries = avgKlineAligned.map((item) => item?.close ?? null);
  const { primaryReturns, benchmarkReturns } = buildPairedReturns(watchCloseSeries, benchmarkCloseAligned);

  return {
    state: {
      benchmarkSymbol,
      labels,
      avgKlineAligned,
      benchmarkCloseAligned,
      watchReturnSeries: primaryReturns,
      benchmarkReturnSeries: benchmarkReturns,
      watchLatestReturn: findLastNumber(primaryReturns),
      benchmarkLatestReturn: findLastNumber(benchmarkReturns),
    },
    error: null,
  };
}

export function buildBoughtCompareState(
  response: CompareKlineResponse | undefined,
  benchmarkSymbol: string,
  targets: Array<BoughtTarget & { symbol: string; buyDate: string }>,
): { state: BoughtCompareState | null; error: string | null } {
  if (!response) {
    return { state: null, error: null };
  }
  const seriesMap = buildSeriesMap(response.series);
  const benchmarkSeries = seriesMap.get(benchmarkSymbol);
  const benchmarkItems = normalizeKlineItems(benchmarkSeries?.items || []);
  if (benchmarkSeries?.error || benchmarkItems.length === 0) {
    return { state: null, error: "大盘 K 线数据不足" };
  }

  const labels = benchmarkItems.map((item) => item.date);
  const benchmarkCloseMap = new Map(benchmarkItems.map((item) => [item.date, item.close]));
  const benchmarkCloseAligned = buildCloseAlignWithCarry(labels, benchmarkCloseMap);

  const perHoldingPointSeries: Array<Array<KlinePoint | null>> = [];
  const perHoldingCloseSeries: Array<Array<number | null>> = [];
  const holdingWeights: number[] = [];

  targets.forEach((target) => {
    const stockSeries = seriesMap.get(target.symbol);
    const shareCount = target.lots * sharesPerLotBySymbol(target.symbol);
    const weight = target.buyPrice * shareCount;
    holdingWeights.push(weight > 0 ? weight : 0);

    const stockItems = !stockSeries?.error ? normalizeKlineItems(stockSeries?.items || []) : [];
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
    targets.forEach((target, targetIndex) => {
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

  return {
    state: {
      benchmarkSymbol,
      labels,
      weightedKlineAligned,
      benchmarkCloseAligned,
      portfolioReturnSeries,
      benchmarkReturnSeries,
      portfolioLatestReturn: findLastNumber(portfolioReturnSeries),
      benchmarkLatestReturn: findLastNumber(benchmarkReturnSeries),
    },
    error: null,
  };
}

export function buildKlineCompareOption(params: {
  labels: string[];
  period: KlinePeriod;
  candlestickLabel: string;
  candlestickSeries: Array<KlinePoint | null>;
  benchmarkLabel: string;
  benchmarkSeries: Array<number | null>;
}) {
  return {
    animation: false,
    tooltip: { trigger: "axis" },
    legend: { top: 0, data: [params.candlestickLabel, params.benchmarkLabel] },
    grid: { left: 48, right: 52, top: 36, bottom: 40 },
    xAxis: {
      type: "category",
      data: params.labels.map((item) => formatLabel(item, params.period)),
      boundaryGap: true,
      axisLine: { lineStyle: { color: marketTheme.chart.axis } },
      axisLabel: { color: marketTheme.chart.axis },
    },
    yAxis: [
      {
        type: "value",
        scale: true,
        splitLine: { lineStyle: { color: marketTheme.chart.grid } },
      },
      {
        type: "value",
        scale: true,
        splitLine: { show: false },
      },
    ],
    series: [
      {
        name: params.candlestickLabel,
        type: "candlestick",
        data: params.candlestickSeries.map((item) => (item ? [item.open, item.close, item.low, item.high] : "-")),
        itemStyle: {
          color: marketTheme.trend.rise,
          color0: marketTheme.trend.fall,
          borderColor: marketTheme.trend.rise,
          borderColor0: marketTheme.trend.fall,
        },
      },
      {
        name: params.benchmarkLabel,
        type: "line",
        yAxisIndex: 1,
        smooth: true,
        showSymbol: false,
        data: params.benchmarkSeries,
        lineStyle: { width: 1.8, color: marketTheme.chart.benchmark },
        areaStyle: { color: marketTheme.chart.benchmarkArea, opacity: 0.08 },
      },
    ],
  };
}

export function buildReturnCompareOption(params: {
  labels: string[];
  period: KlinePeriod;
  primaryLabel: string;
  primarySeries: Array<number | null>;
  primaryColor: string;
  benchmarkLabel: string;
  benchmarkSeries: Array<number | null>;
}) {
  return {
    animation: false,
    tooltip: { trigger: "axis" },
    legend: { top: 0, data: [params.primaryLabel, params.benchmarkLabel] },
    grid: { left: 48, right: 24, top: 36, bottom: 40 },
    xAxis: {
      type: "category",
      data: params.labels.map((item) => formatLabel(item, params.period)),
      axisLine: { lineStyle: { color: marketTheme.chart.axis } },
      axisLabel: { color: marketTheme.chart.axis },
    },
    yAxis: {
      type: "value",
      axisLabel: { formatter: (val: number) => `${(val * 100).toFixed(0)}%` },
      splitLine: { lineStyle: { color: marketTheme.chart.grid } },
    },
    series: [
      {
        name: params.primaryLabel,
        type: "line",
        smooth: true,
        showSymbol: false,
        data: params.primarySeries,
        lineStyle: { width: 2, color: params.primaryColor },
      },
      {
        name: params.benchmarkLabel,
        type: "line",
        smooth: true,
        showSymbol: false,
        data: params.benchmarkSeries,
        lineStyle: { width: 2, color: marketTheme.chart.benchmark },
      },
    ],
  };
}
