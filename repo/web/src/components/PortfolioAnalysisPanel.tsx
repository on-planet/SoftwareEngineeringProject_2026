import React, { useEffect, useMemo, useState } from "react";

import ReactECharts from "echarts-for-react";

import { getStockOverview } from "../services/api";
import { formatNumber, formatPercent } from "../utils/format";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";

type WatchOverviewItem = {
  symbol: string;
  name: string;
  market: string;
  sector: string;
  current: number | null;
  percent: number | null;
};

type WatchAnalysisCachePayload = {
  items: WatchOverviewItem[];
};

const WATCH_ANALYSIS_CACHE_TTL_MS = 5 * 60 * 1000;
const MAX_ANALYSIS_SYMBOLS = 30;

function normalizeSymbol(symbol: string) {
  return (symbol || "").trim().toUpperCase();
}

function buildWatchAnalysisCacheKey(symbols: string[]) {
  return ["watch-analysis", ...symbols].join(":");
}

export function PortfolioAnalysisPanel({ watchSymbols }: { watchSymbols: string[] }) {
  const normalizedSymbols = useMemo(() => {
    const unique = new Set<string>();
    const result: string[] = [];
    for (const item of watchSymbols) {
      const symbol = normalizeSymbol(item);
      if (!symbol || unique.has(symbol)) {
        continue;
      }
      unique.add(symbol);
      result.push(symbol);
      if (result.length >= MAX_ANALYSIS_SYMBOLS) {
        break;
      }
    }
    return result;
  }, [watchSymbols]);

  const [topN, setTopN] = useState(10);
  const [items, setItems] = useState<WatchOverviewItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (normalizedSymbols.length === 0) {
      setItems([]);
      setLoading(false);
      setError(null);
      return;
    }
    let active = true;
    const cacheKey = buildWatchAnalysisCacheKey(normalizedSymbols);
    const cachedPayload = readPersistentCache<WatchAnalysisCachePayload>(
      cacheKey,
      WATCH_ANALYSIS_CACHE_TTL_MS,
    );
    if (cachedPayload?.items?.length) {
      setItems(cachedPayload.items);
      setLoading(false);
    } else {
      setLoading(true);
    }

    Promise.allSettled(
      normalizedSymbols.map((symbol) => getStockOverview(symbol, { prefer_live: true })),
    )
      .then((results) => {
        if (!active) {
          return;
        }
        const nextItems: WatchOverviewItem[] = [];
        results.forEach((result, index) => {
          if (result.status !== "fulfilled") {
            return;
          }
          const payload = result.value as any;
          const quote = payload?.quote || {};
          const symbol = normalizeSymbol(payload?.symbol || normalizedSymbols[index] || "");
          if (!symbol) {
            return;
          }
          nextItems.push({
            symbol,
            name: String(payload?.name || symbol),
            market: String(payload?.market || ""),
            sector: String(payload?.sector || "未分类"),
            current: typeof quote.current === "number" ? quote.current : null,
            percent: typeof quote.percent === "number" ? quote.percent : null,
          });
        });
        setItems(nextItems);
        writePersistentCache(cacheKey, { items: nextItems });
        setError(nextItems.length > 0 ? null : "自选标的数据加载失败");
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setError(err.message || "自选分析加载失败");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [normalizedSymbols]);

  const summary = useMemo(() => {
    const total = items.length;
    const sectorSet = new Set(items.map((item) => item.sector || "未分类"));
    let rising = 0;
    let falling = 0;
    let flat = 0;
    for (const item of items) {
      const pct = item.percent;
      if (typeof pct !== "number") {
        flat += 1;
      } else if (pct > 0) {
        rising += 1;
      } else if (pct < 0) {
        falling += 1;
      } else {
        flat += 1;
      }
    }
    return {
      total,
      sectors: sectorSet.size,
      rising,
      falling,
      flat,
    };
  }, [items]);

  const sectorExposure = useMemo(() => {
    const bucket = new Map<string, number>();
    items.forEach((item) => {
      const sector = item.sector || "未分类";
      bucket.set(sector, (bucket.get(sector) || 0) + 1);
    });
    const total = items.length || 1;
    return Array.from(bucket.entries())
      .map(([sector, count]) => ({
        sector,
        count,
        weight: count / total,
      }))
      .sort((a, b) => b.count - a.count);
  }, [items]);

  const topMovers = useMemo(() => {
    return [...items]
      .sort((a, b) => Math.abs(b.percent || 0) - Math.abs(a.percent || 0))
      .slice(0, Math.max(1, topN));
  }, [items, topN]);

  const sectorPieOption = useMemo(() => {
    if (sectorExposure.length === 0) {
      return null;
    }
    return {
      tooltip: { trigger: "item" },
      legend: { bottom: 0 },
      series: [
        {
          name: "行业分布",
          type: "pie",
          radius: ["35%", "65%"],
          data: sectorExposure.map((item) => ({
            name: item.sector,
            value: item.count,
          })),
        },
      ],
    };
  }, [sectorExposure]);

  const moversBarOption = useMemo(() => {
    if (topMovers.length === 0) {
      return null;
    }
    return {
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: topMovers.map((item) => item.symbol) },
      yAxis: { type: "value" },
      series: [
        {
          type: "bar",
          data: topMovers.map((item) => Number(item.percent || 0)),
          barMaxWidth: 36,
        },
      ],
      grid: { left: 40, right: 20, top: 30, bottom: 40 },
    };
  }, [topMovers]);

  if (normalizedSymbols.length === 0) {
    return <div className="helper">暂无自选标的，请先在个股详情点击“加入观察”。</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <section className="card">
        <div className="card-title" style={{ marginBottom: 12 }}>
          自选分析设置
        </div>
        <div className="toolbar">
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            自选数量
            <input className="input" type="number" value={normalizedSymbols.length} readOnly />
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            波动TopN
            <input
              className="input"
              type="number"
              min={1}
              max={30}
              value={topN}
              onChange={(event) => setTopN(Math.max(1, Math.min(30, Number(event.target.value) || 10)))}
            />
          </label>
        </div>
      </section>

      {loading ? (
        <div className="helper">自选分析加载中...</div>
      ) : error ? (
        <div className="helper">{`自选分析加载失败：${error}`}</div>
      ) : (
        <>
          <section className="grid grid-3">
            <div className="card">
              <div className="helper">自选标的数</div>
              <div style={{ fontWeight: 700, marginTop: 4 }}>{summary.total}</div>
            </div>
            <div className="card">
              <div className="helper">覆盖行业数</div>
              <div style={{ fontWeight: 700, marginTop: 4 }}>{summary.sectors}</div>
            </div>
            <div className="card">
              <div className="helper">上涨 / 下跌 / 平盘</div>
              <div style={{ fontWeight: 700, marginTop: 4 }}>
                {summary.rising} / {summary.falling} / {summary.flat}
              </div>
            </div>
          </section>

          <section className="grid grid-3">
            <div className="card">
              <div className="card-title">自选行业暴露（按数量）</div>
              {sectorPieOption ? (
                <ReactECharts option={sectorPieOption} style={{ height: 240 }} />
              ) : (
                <div className="helper">暂无行业数据</div>
              )}
            </div>
            <div className="card">
              <div className="card-title">自选波动TopN（涨跌幅）</div>
              {moversBarOption ? (
                <ReactECharts option={moversBarOption} style={{ height: 240 }} />
              ) : (
                <div className="helper">暂无涨跌数据</div>
              )}
            </div>
            <div className="card">
              <div className="card-title">行业权重明细</div>
              {sectorExposure.length === 0 ? (
                <div className="helper">暂无行业数据</div>
              ) : (
                <div style={{ display: "grid", gap: 8 }}>
                  {sectorExposure.map((item) => (
                    <div key={item.sector} style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                      <span>{item.sector}</span>
                      <span style={{ fontWeight: 600 }}>
                        {item.count} / {formatPercent(item.weight)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          <section className="card">
            <div className="card-title">自选标的明细</div>
            <div style={{ display: "grid", gap: 8 }}>
              {items.map((item) => (
                <div key={item.symbol} style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                  <span>
                    {item.symbol} {item.name ? `· ${item.name}` : ""} {item.sector ? `· ${item.sector}` : ""}
                  </span>
                  <span style={{ fontWeight: 600 }}>
                    {item.current === null ? "--" : formatNumber(item.current)} ·{" "}
                    {item.percent === null ? "--" : formatPercent(item.percent / 100)}
                  </span>
                </div>
              ))}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
