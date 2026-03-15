import React, { useEffect, useMemo, useState } from "react";

import ReactECharts from "echarts-for-react";

import { getIndexKline } from "../services/api";

type KlinePoint = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

type KlineSeries = {
  symbol: string;
  period: "day" | "week" | "month" | "quarter" | "year";
  items: KlinePoint[];
};

const INDEX_OPTIONS = [
  { symbol: "000001.SH", label: "SSE Composite" },
  { symbol: "399001.SZ", label: "SZSE Component" },
  { symbol: "399006.SZ", label: "ChiNext" },
] as const;

const PERIOD_OPTIONS: Array<KlineSeries["period"]> = ["day", "week", "month", "quarter", "year"];

const PERIOD_LABELS: Record<KlineSeries["period"], string> = {
  day: "Day",
  week: "Week",
  month: "Month",
  quarter: "Quarter",
  year: "Year",
};

export function IndexKlinePanel() {
  const [symbol, setSymbol] = useState<string>(INDEX_OPTIONS[0].symbol);
  const [period, setPeriod] = useState<KlineSeries["period"]>("day");
  const [items, setItems] = useState<KlinePoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getIndexKline(symbol, { period, limit: 240 })
      .then((res) => {
        if (!active) {
          return;
        }
        const payload = res as KlineSeries;
        setItems(payload.items ?? []);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setItems([]);
        setError(err.message || "Failed to load index kline");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [period, symbol]);

  const option = useMemo(() => {
    if (!items.length) {
      return null;
    }
    return {
      animation: false,
      tooltip: { trigger: "axis" },
      grid: { left: 48, right: 24, top: 28, bottom: 40 },
      xAxis: { type: "category", data: items.map((item) => item.date), boundaryGap: true },
      yAxis: { type: "value", scale: true },
      series: [
        {
          type: "candlestick",
          data: items.map((item) => [item.open, item.close, item.low, item.high]),
          itemStyle: {
            color: "#ef4444",
            color0: "#10b981",
            borderColor: "#ef4444",
            borderColor0: "#10b981",
          },
        },
      ],
    };
  }, [items]);

  return (
    <div className="card">
      <div className="panel-header">
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <select className="select" value={symbol} onChange={(event) => setSymbol(event.target.value)}>
            {INDEX_OPTIONS.map((item) => (
              <option key={item.symbol} value={item.symbol}>
                {item.label}
              </option>
            ))}
          </select>
          <div className="chip-group">
            {PERIOD_OPTIONS.map((item) => (
              <button
                key={item}
                type="button"
                className="chip-button"
                data-active={item === period}
                onClick={() => setPeriod(item)}
              >
                {PERIOD_LABELS[item]}
              </button>
            ))}
          </div>
        </div>
      </div>
      {loading ? <div className="helper">Loading index kline...</div> : null}
      {!loading && error ? <div className="helper">Index kline failed: {error}</div> : null}
      {!loading && !error && option ? <ReactECharts option={option} style={{ height: 360 }} /> : null}
      {!loading && !error && !option ? <div className="helper">No index kline data available.</div> : null}
    </div>
  );
}
