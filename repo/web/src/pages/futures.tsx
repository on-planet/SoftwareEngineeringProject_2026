import React, { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";

import { getFutures, getFuturesSeries } from "../services/api";
import { formatNullableNumber, formatNumber, formatPercent, formatSigned } from "../utils/format";
import { formatContractMonth, FUTURES_LABELS, sortPreferredFutures } from "../utils/futures";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";

type FuturesFrequency = "day" | "week";

type FuturesItem = {
  symbol: string;
  name?: string | null;
  date: string;
  contract_month?: string | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
  settlement?: number | null;
  open_interest?: number | null;
  turnover?: number | null;
  volume?: number | null;
  source?: string | null;
};

type FuturesPage = {
  items: FuturesItem[];
  total: number;
  limit: number;
  offset: number;
};

type FuturesSeries = {
  symbol: string;
  items: FuturesItem[];
};

const FUTURES_LIST_CACHE_TTL_MS = 10 * 60 * 1000;
const FUTURES_SERIES_CACHE_TTL_MS = 10 * 60 * 1000;

function toLatestBySymbol(items: FuturesItem[]) {
  const map = new Map<string, FuturesItem>();
  for (const item of items) {
    if (!item.symbol || !item.date) {
      continue;
    }
    const current = map.get(item.symbol);
    if (!current || new Date(item.date).getTime() > new Date(current.date).getTime()) {
      map.set(item.symbol, item);
    }
  }
  return sortPreferredFutures(Array.from(map.values()));
}

function buildFuturesListCacheKey(frequency: FuturesFrequency, start: string, end: string) {
  return `futures:list:frequency=${frequency}:start=${start || "none"}:end=${end || "none"}`;
}

function buildFuturesSeriesCacheKey(symbol: string, frequency: FuturesFrequency, start: string, end: string) {
  return `futures:series:${symbol}:frequency=${frequency}:start=${start || "none"}:end=${end || "none"}`;
}

export default function FuturesPage() {
  const [frequency, setFrequency] = useState<FuturesFrequency>("day");
  const [items, setItems] = useState<FuturesItem[]>([]);
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [series, setSeries] = useState<FuturesItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [seriesLoading, setSeriesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  useEffect(() => {
    let active = true;
    const cacheKey = buildFuturesListCacheKey(frequency, start, end);
    const cachedItems = readPersistentCache<FuturesItem[]>(cacheKey, FUTURES_LIST_CACHE_TTL_MS);
    if (cachedItems?.length) {
      setItems(cachedItems);
      setSelectedSymbol((prev) => {
        if (!cachedItems.length) {
          return "";
        }
        return cachedItems.some((item) => item.symbol === prev) ? prev : cachedItems[0].symbol;
      });
      setLoading(false);
    } else {
      setLoading(true);
    }
    getFutures({
      sort: "desc",
      limit: 500,
      start: start || undefined,
      end: end || undefined,
      as_of: end || undefined,
      frequency,
    })
      .then((res) => {
        if (!active) {
          return;
        }
        const page = res as FuturesPage;
        const latest = toLatestBySymbol(page.items ?? []);
        setItems(latest);
        writePersistentCache(cacheKey, latest);
        setSelectedSymbol((prev) => {
          if (!latest.length) {
            return "";
          }
          return latest.some((item) => item.symbol === prev) ? prev : latest[0].symbol;
        });
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setError(err.message || "Failed to load futures data");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [end, frequency, start]);

  useEffect(() => {
    if (!selectedSymbol) {
      setSeries([]);
      return;
    }
    let active = true;
    const cacheKey = buildFuturesSeriesCacheKey(selectedSymbol, frequency, start, end);
    const cachedSeries = readPersistentCache<FuturesItem[]>(cacheKey, FUTURES_SERIES_CACHE_TTL_MS);
    if (cachedSeries?.length) {
      setSeries(cachedSeries);
      setSeriesLoading(false);
    } else {
      setSeriesLoading(true);
    }
    getFuturesSeries(selectedSymbol, {
      start: start || undefined,
      end: end || undefined,
      frequency,
    })
      .then((res) => {
        if (!active) {
          return;
        }
        const payload = res as FuturesSeries;
        setSeries(payload.items ?? []);
        writePersistentCache(cacheKey, payload.items ?? []);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setSeries([]);
        setError(err.message || "Failed to load futures series");
      })
      .finally(() => {
        if (active) {
          setSeriesLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [end, frequency, selectedSymbol, start]);

  const chartOption = useMemo(() => {
    if (!series.length) {
      return null;
    }
    const labels = series.map((item) => item.date);
    const closeValues = series.map((item) => Number(item.close ?? 0));
    const volumeValues = series.map((item) => Number(item.volume ?? 0));

    return {
      tooltip: { trigger: "axis" },
      legend: { data: ["Close", "Volume"] },
      grid: { left: 48, right: 48, top: 36, bottom: 40 },
      xAxis: [{ type: "category", data: labels }],
      yAxis: [{ type: "value", scale: true }, { type: "value", scale: true }],
      series: [
        {
          name: "Close",
          type: "line",
          data: closeValues,
          smooth: true,
          showSymbol: false,
          lineStyle: { width: 2, color: "#2563eb" },
        },
        {
          name: "Volume",
          type: "bar",
          yAxisIndex: 1,
          data: volumeValues,
          itemStyle: { color: "rgba(37, 99, 235, 0.3)" },
          barMaxWidth: 20,
        },
      ],
    };
  }, [series]);

  if (loading) {
    return <div className="page">期货看板加载中...</div>;
  }

  if (error) {
    return <div className="page">期货数据加载失败: {error}</div>;
  }

  return (
    <div className="page">
      <section className="card">
        <div className="card-title" style={{ marginBottom: 12 }}>
          筛选条件
        </div>
        <div className="toolbar" style={{ alignItems: "end", flexWrap: "wrap", gap: 12 }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            频率
            <select className="select" value={frequency} onChange={(event) => setFrequency(event.target.value as FuturesFrequency)}>
              <option value="day">日度</option>
              <option value="week">周度</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            开始日期
            <input className="input" type="date" value={start} onChange={(event) => setStart(event.target.value)} />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            结束日期
            <input className="input" type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12 }}>
            品种
            <select className="select" value={selectedSymbol} onChange={(event) => setSelectedSymbol(event.target.value)}>
              {items.length === 0 ? <option value="">暂无品种</option> : null}
              {items.map((item) => (
                <option key={item.symbol} value={item.symbol}>
                  {FUTURES_LABELS[item.symbol] || item.name || item.symbol}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section>
        <h2 className="section-title">期货快照</h2>
        {items.length === 0 ? (
          <div className="helper">暂无期货数据</div>
        ) : (
          <div className="grid grid-3">
            {items.map((item) => {
              const open = Number(item.open ?? 0);
              const close = Number(item.close ?? 0);
              const delta = close - open;
              const pct = open !== 0 ? delta / open : 0;
              const trendColor = delta >= 0 ? "#f87171" : "#34d399";
              const label = FUTURES_LABELS[item.symbol] || item.name || item.symbol;
              return (
                <button
                  type="button"
                  key={`${item.symbol}-${item.date}`}
                  className="card"
                  style={{
                    textAlign: "left",
                    cursor: "pointer",
                    borderColor: item.symbol === selectedSymbol ? "rgba(37, 99, 235, 0.35)" : undefined,
                  }}
                  onClick={() => setSelectedSymbol(item.symbol)}
                >
                  <div className="card-title">{label}</div>
                  <div className="helper">
                    {item.symbol} | {item.date}
                  </div>
                  <div className="helper" style={{ marginTop: 4 }}>
                    主力合约: {formatContractMonth(item.contract_month)}
                  </div>
                  <div style={{ marginTop: 8, fontSize: 20, fontWeight: 700 }}>{formatNumber(close)}</div>
                  <div style={{ marginTop: 4, color: trendColor, fontWeight: 600 }}>
                    {formatSigned(delta)} ({delta === 0 ? "0.00%" : formatPercent(pct)})
                  </div>
                  <div className="helper" style={{ marginTop: 8 }}>
                    结算 {formatNullableNumber(item.settlement)}
                  </div>
                  <div className="helper">
                    持仓 {formatNullableNumber(item.open_interest, 0)} | 成交额 {formatNullableNumber(item.turnover)}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </section>

      <section>
        <h2 className="section-title">价格走势</h2>
        <div className="card">
          {seriesLoading ? (
            <div className="helper">走势加载中...</div>
          ) : chartOption ? (
            <ReactECharts option={chartOption} style={{ height: 360 }} />
          ) : (
            <div className="helper">暂无走势数据</div>
          )}
        </div>
      </section>
    </div>
  );
}
