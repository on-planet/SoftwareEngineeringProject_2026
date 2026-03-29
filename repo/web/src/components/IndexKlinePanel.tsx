import React, { useEffect, useMemo, useState } from "react";

import ReactECharts from "echarts-for-react";

import { INDEX_NAME_MAP, INDEX_OPTIONS } from "../constants/indices";
import { getIndexKline } from "../services/api";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";

type IndexMarket = "A" | "HK";
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

const MARKET_OPTIONS: Array<{ key: IndexMarket; label: string }> = [
  { key: "A", label: "A 股" },
  { key: "HK", label: "港股" },
];

function getIndexKlineCacheMaxAge(period: KlinePeriod) {
  switch (period) {
    case "1m":
    case "30m":
    case "60m":
      return 2 * 60 * 1000;
    case "day":
    case "week":
      return 10 * 60 * 1000;
    default:
      return 60 * 60 * 1000;
  }
}

function buildIndexKlineCacheKey(symbol: string, period: KlinePeriod, limit: number) {
  return `index-kline:${symbol}:period=${period}:limit=${limit}`;
}

type Props = {
  symbol: string;
  activeMarket: IndexMarket;
  onMarketChange: (market: IndexMarket) => void;
  onSymbolChange: (symbol: string) => void;
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

export function IndexKlinePanel({ symbol, activeMarket, onMarketChange, onSymbolChange }: Props) {
  const marketOptions = useMemo(() => INDEX_OPTIONS.filter((item) => item.market === activeMarket), [activeMarket]);
  const selectOptions = useMemo(() => {
    if (marketOptions.some((item) => item.symbol === symbol)) {
      return marketOptions;
    }
    return [{ symbol, label: INDEX_NAME_MAP[symbol] || symbol, market: activeMarket }, ...marketOptions];
  }, [activeMarket, marketOptions, symbol]);
  const [period, setPeriod] = useState<KlinePeriod>("day");
  const [items, setItems] = useState<KlinePoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const limit = period === "1m" ? 180 : 240;
    const cacheKey = buildIndexKlineCacheKey(symbol, period, limit);
    const cachedSeries = readPersistentCache<KlineSeries>(cacheKey, getIndexKlineCacheMaxAge(period));
    if (cachedSeries?.items?.length) {
      setItems(cachedSeries.items);
      setLoading(false);
    } else {
      setLoading(true);
    }
    getIndexKline(symbol, { period, limit })
      .then((res) => {
        if (!active) {
          return;
        }
        const payload = res as KlineSeries;
        setItems(payload.items ?? []);
        writePersistentCache(cacheKey, payload);
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
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="index-market-switch" role="tablist" aria-label="K 线市场切换">
            {MARKET_OPTIONS.map((item) => (
              <button
                key={item.key}
                type="button"
                role="tab"
                aria-selected={item.key === activeMarket}
                className="index-market-button"
                data-active={item.key === activeMarket}
                onClick={() => onMarketChange(item.key)}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <select className="select" value={symbol} onChange={(event) => onSymbolChange(event.target.value)}>
              {selectOptions.map((item) => (
                <option key={item.symbol} value={item.symbol}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
        </div>
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
      <div key={`${activeMarket}:${symbol}:${period}`} className="motion-tab-panel">
        {loading ? <div className="helper">指数 K 线加载中...</div> : null}
        {!loading && error ? <div className="helper">{`指数 K 线加载失败：${error}`}</div> : null}
        {!loading && !error && option ? <ReactECharts option={option} style={{ height: 360 }} /> : null}
        {!loading && !error && !option ? <div className="helper">暂无指数 K 线数据。</div> : null}
      </div>
    </div>
  );
}
