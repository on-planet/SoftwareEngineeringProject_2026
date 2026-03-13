import React, { useEffect, useMemo, useState } from "react";

import ReactECharts from "echarts-for-react";

import { getIndicators } from "../services/api";

type IndicatorPoint = {
  date: string;
  value: number;
};

type IndicatorResponse = {
  symbol: string;
  indicator: string;
  window: number;
  items: IndicatorPoint[];
  cache_hit?: boolean;
};

type Props = {
  symbol: string;
};

export function StockIndicatorsChart({ symbol }: Props) {
  const [indicator, setIndicator] = useState<"ma" | "rsi">("ma");
  const [window, setWindow] = useState(14);
  const [limit, setLimit] = useState(200);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [items, setItems] = useState<IndicatorPoint[]>([]);
  const [cacheHit, setCacheHit] = useState<boolean | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
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
        setCacheHit(payload.cache_hit);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setError(err.message || "加载指标失败");
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
    const values = items.map((item) => item.value);
    return {
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: labels, boundaryGap: false },
      yAxis: { type: "value" },
      series: [{ type: "line", data: values, smooth: true }],
      grid: { left: 40, right: 20, top: 30, bottom: 40 },
    };
  }, [items]);

  const cacheHitLabel = cacheHit === undefined ? "未知" : cacheHit ? "命中" : "未命中";

  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 16, background: "#fff" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12, gap: 12, flexWrap: "wrap" }}>
        <div style={{ fontWeight: 600 }}>技术指标（{indicator.toUpperCase()}）</div>
        <div style={{ fontSize: 12, color: "#718096" }}>缓存：{cacheHitLabel}</div>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <select
          value={indicator}
          onChange={(event) => setIndicator(event.target.value as "ma" | "rsi")}
          style={{ padding: "4px 8px" }}
        >
          <option value="ma">MA</option>
          <option value="rsi">RSI</option>
        </select>
        <input
          type="number"
          min={2}
          max={200}
          value={window}
          onChange={(event) => setWindow(Number(event.target.value) || 14)}
          style={{ width: 80, padding: "4px 8px" }}
        />
        <input
          type="number"
          min={10}
          max={500}
          value={limit}
          onChange={(event) => setLimit(Number(event.target.value) || 200)}
          style={{ width: 80, padding: "4px 8px" }}
        />
        <input
          type="date"
          value={start}
          onChange={(event) => setStart(event.target.value)}
          style={{ padding: "4px 8px" }}
        />
        <input
          type="date"
          value={end}
          onChange={(event) => setEnd(event.target.value)}
          style={{ padding: "4px 8px" }}
        />
      </div>
      {loading ? (
        <div>指标加载中...</div>
      ) : error ? (
        <div>指标加载失败：{error}</div>
      ) : (
        <ReactECharts option={chartOption} style={{ height: 240 }} />
      )}
    </div>
  );
}
