import React, { useEffect, useMemo, useState } from "react";

import ReactECharts from "echarts-for-react";

import { getIndexKline } from "../services/api";

type KlinePeriod = "1m" | "30m" | "60m" | "day" | "week" | "month" | "quarter" | "year";

type KlinePoint = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
};

type KlineSeries = {
  symbol: string;
  period: KlinePeriod;
  items: KlinePoint[];
};

const INDEX_OPTIONS = [
  { symbol: "000001.SH", label: "上证指数" },
  { symbol: "399001.SZ", label: "深证成指" },
  { symbol: "399006.SZ", label: "创业板指" },
] as const;

const PERIOD_OPTIONS: KlinePeriod[] = ["1m", "30m", "60m", "day", "week", "month", "quarter", "year"];

const PERIOD_LABELS: Record<KlinePeriod, string> = {
  "1m": "1 分钟",
  "30m": "30 分钟",
  "60m": "60 分钟",
  day: "日 K",
  week: "周 K",
  month: "月 K",
  quarter: "季 K",
  year: "年 K",
};

function formatAxisLabel(value: string, period: KlinePeriod) {
  if (period === "1m" || period === "30m" || period === "60m") {
    return new Date(value).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }
  return String(value).slice(0, 10);
}

export function IndexKlinePanel() {
  const [symbol, setSymbol] = useState<string>(INDEX_OPTIONS[0].symbol);
  const [period, setPeriod] = useState<KlinePeriod>("day");
  const [items, setItems] = useState<KlinePoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getIndexKline(symbol, { period, limit: period === "1m" ? 180 : 240 })
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
        setError(err.message || "指数 K 线加载失败");
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
      xAxis: {
        type: "category",
        data: items.map((item) => formatAxisLabel(item.date, period)),
        boundaryGap: true,
      },
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
  }, [items, period]);

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
      {loading ? <div className="helper">指数 K 线加载中...</div> : null}
      {!loading && error ? <div className="helper">指数 K 线加载失败：{error}</div> : null}
      {!loading && !error && option ? <ReactECharts option={option} style={{ height: 360 }} /> : null}
      {!loading && !error && !option ? <div className="helper">暂无指数 K 线数据。</div> : null}
    </div>
  );
}
