import React, { useEffect, useMemo, useState } from "react";

import ReactECharts from "echarts-for-react";

import { getIndicators } from "../services/api";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";

type IndicatorKey =
  | "ma"
  | "sma"
  | "ema"
  | "wma"
  | "rsi"
  | "macd"
  | "boll"
  | "kdj"
  | "atr"
  | "cci"
  | "wr"
  | "obv"
  | "roc"
  | "mom"
  | "adx"
  | "mfi";

type IndicatorPoint = {
  date: string;
  value?: number | null;
  values?: Record<string, number>;
};

type IndicatorResponse = {
  symbol: string;
  indicator: IndicatorKey;
  window: number;
  lines?: string[];
  params?: Record<string, number | string>;
  items: IndicatorPoint[];
  cache_hit?: boolean;
};

type Props = {
  symbol: string;
};

const INDICATOR_OPTIONS: Array<{ value: IndicatorKey; label: string }> = [
  { value: "ma", label: "移动均线 MA" },
  { value: "sma", label: "简单均线 SMA" },
  { value: "ema", label: "指数均线 EMA" },
  { value: "wma", label: "加权均线 WMA" },
  { value: "rsi", label: "相对强弱 RSI" },
  { value: "macd", label: "平滑异同 MACD" },
  { value: "boll", label: "布林带 BOLL" },
  { value: "kdj", label: "随机指标 KDJ" },
  { value: "atr", label: "真实波幅 ATR" },
  { value: "cci", label: "顺势指标 CCI" },
  { value: "wr", label: "威廉指标 WR" },
  { value: "obv", label: "能量潮 OBV" },
  { value: "roc", label: "变动率 ROC" },
  { value: "mom", label: "动量 MOM" },
  { value: "adx", label: "趋势指标 ADX" },
  { value: "mfi", label: "资金流量 MFI" },
];

const WINDOWLESS_INDICATORS = new Set<IndicatorKey>(["macd", "obv"]);
const LINE_COLORS = ["#0f766e", "#c2410c", "#1d4ed8", "#b45309", "#7c3aed"];
const STOCK_INDICATORS_CACHE_TTL_MS = 10 * 60 * 1000;

function buildStockIndicatorsCacheKey(params: {
  symbol: string;
  indicator: IndicatorKey;
  window: number;
  limit: number;
  start: string;
  end: string;
}) {
  return [
    "stock-indicators",
    params.symbol,
    `indicator=${params.indicator}`,
    `window=${params.window}`,
    `limit=${params.limit}`,
    `start=${params.start || "none"}`,
    `end=${params.end || "none"}`,
  ].join(":");
}

export function StockIndicatorsChart({ symbol }: Props) {
  const [indicator, setIndicator] = useState<IndicatorKey>("ma");
  const [window, setWindow] = useState(14);
  const [limit, setLimit] = useState(200);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [items, setItems] = useState<IndicatorPoint[]>([]);
  const [lines, setLines] = useState<string[]>([]);
  const [params, setParams] = useState<Record<string, number | string>>({});
  const [cacheHit, setCacheHit] = useState<boolean | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const cacheKey = buildStockIndicatorsCacheKey({ symbol, indicator, window, limit, start, end });
    const cachedPayload = readPersistentCache<IndicatorResponse>(cacheKey, STOCK_INDICATORS_CACHE_TTL_MS);
    if (cachedPayload?.items?.length) {
      setItems(cachedPayload.items ?? []);
      setLines((cachedPayload.lines ?? []).filter(Boolean));
      setParams(cachedPayload.params ?? {});
      setCacheHit(cachedPayload.cache_hit);
      setLoading(false);
    } else {
      setLoading(true);
    }
    getIndicators(symbol, {
      indicator,
      window,
      limit,
      start: start || undefined,
      end: end || undefined,
    })
      .then((res) => {
        if (!active) {
          return;
        }
        const payload = res as IndicatorResponse;
        setItems(payload.items ?? []);
        setLines((payload.lines ?? []).filter(Boolean));
        setParams(payload.params ?? {});
        setCacheHit(payload.cache_hit);
        writePersistentCache(cacheKey, payload);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setError(err.message || "技术指标加载失败");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [symbol, indicator, window, limit, start, end]);

  const chartOption = useMemo(() => {
    const labels = items.map((item) => new Date(item.date).toLocaleDateString("zh-CN"));
    const resolvedLines = lines.length ? lines : [indicator];
    const series = resolvedLines.map((line, index) => ({
      name: line.toUpperCase(),
      type: line === "hist" ? "bar" : "line",
      data: items.map((item) => {
        if (item.values && typeof item.values[line] === "number") {
          return item.values[line];
        }
        return line === indicator ? item.value ?? 0 : 0;
      }),
      smooth: line !== "hist",
      showSymbol: false,
      lineStyle: { width: 2 },
      itemStyle: { color: LINE_COLORS[index % LINE_COLORS.length] },
    }));
    return {
      tooltip: { trigger: "axis" },
      legend: { top: 0 },
      xAxis: { type: "category", data: labels, boundaryGap: false },
      yAxis: { type: "value", scale: true },
      series,
      grid: { left: 48, right: 24, top: 48, bottom: 40 },
    };
  }, [indicator, items, lines]);

  const cacheHitLabel = cacheHit === undefined ? "未知" : cacheHit ? "命中" : "未命中";
  const paramsLabel = Object.entries(params)
    .map(([key, value]) => `${key}=${value}`)
    .join(" / ");

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12, gap: 12, flexWrap: "wrap" }}>
        <div style={{ fontWeight: 600 }}>技术指标（{indicator.toUpperCase()}）</div>
        <div style={{ fontSize: 12, color: "#718096" }}>
          缓存：{cacheHitLabel}
          {paramsLabel ? ` | 参数：${paramsLabel}` : ""}
        </div>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        <select className="select" value={indicator} onChange={(event) => setIndicator(event.target.value as IndicatorKey)}>
          {INDICATOR_OPTIONS.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
        <input
          className="input"
          type="number"
          min={2}
          max={200}
          value={window}
          onChange={(event) => setWindow(Number(event.target.value) || 14)}
          placeholder="窗口"
          style={{ width: 110, opacity: WINDOWLESS_INDICATORS.has(indicator) ? 0.5 : 1 }}
          disabled={WINDOWLESS_INDICATORS.has(indicator)}
        />
        <input
          className="input"
          type="number"
          min={10}
          max={500}
          value={limit}
          onChange={(event) => setLimit(Number(event.target.value) || 200)}
          placeholder="条数"
          style={{ width: 110 }}
        />
        <input className="input" type="date" value={start} onChange={(event) => setStart(event.target.value)} />
        <input className="input" type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
      </div>
      {loading ? (
        <div className="helper">技术指标加载中...</div>
      ) : error ? (
        <div className="helper">技术指标加载失败：{error}</div>
      ) : items.length ? (
        <ReactECharts option={chartOption} style={{ height: 260 }} />
      ) : (
        <div className="helper">暂无技术指标数据。</div>
      )}
    </div>
  );
}
