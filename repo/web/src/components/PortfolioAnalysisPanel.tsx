import React, { useEffect, useMemo, useState } from "react";

import ReactECharts from "echarts-for-react";

import { useApiQuery } from "../hooks/useApiQuery";
import { getCompareStocks, StockCompareItem } from "../services/api";
import { formatNumber, formatPercent } from "../utils/format";

type WatchOverviewItem = {
  symbol: string;
  name: string;
  market: string;
  sector: string;
  current: number | null;
  percent: number | null;
  failed: boolean;
};

type PortfolioAnalysisPanelProps = {
  symbols: string[];
  title?: string;
  emptyText?: string;
  pageSize?: number;
};

const MAX_ANALYSIS_SYMBOLS = 60;
const DEFAULT_PAGE_SIZE = 10;
const UNKNOWN_SECTOR = "未分类";

function normalizeSymbol(symbol: string) {
  return (symbol || "").trim().toUpperCase();
}

function buildOverviewItems(symbols: string[], rawItems: StockCompareItem[] | undefined): WatchOverviewItem[] {
  const itemMap = new Map(
    (rawItems || []).map((item) => [normalizeSymbol(item.symbol), item]),
  );
  return symbols.map((symbol) => {
    const current = itemMap.get(symbol);
    const quote = current?.quote || null;
    const failed = !current || !!current.error;
    return {
      symbol,
      name: String(current?.name || symbol),
      market: String(current?.market || ""),
      sector: String(current?.sector || UNKNOWN_SECTOR),
      current: typeof quote?.current === "number" ? quote.current : null,
      percent: typeof quote?.percent === "number" ? quote.percent : null,
      failed,
    };
  });
}

export function PortfolioAnalysisPanel({
  symbols,
  title = "组合分析",
  emptyText = "暂无标的，请先添加后再查看分析。",
  pageSize = DEFAULT_PAGE_SIZE,
}: PortfolioAnalysisPanelProps) {
  const normalizedSymbols = useMemo(() => {
    const unique = new Set<string>();
    const result: string[] = [];
    for (const item of symbols) {
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
  }, [symbols]);

  const [topN, setTopN] = useState(10);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [normalizedSymbols, pageSize]);

  const compareQuery = useApiQuery(
    normalizedSymbols.length > 0 ? ["stock-compare", "portfolio-analysis", ...normalizedSymbols] : null,
    () =>
      getCompareStocks(
        {
          symbols: normalizedSymbols,
          prefer_live: true,
        },
        { retry: 1 },
      ),
    {
      staleTimeMs: 60_000,
      cacheTimeMs: 5 * 60_000,
    },
  );

  const items = useMemo(
    () => buildOverviewItems(normalizedSymbols, compareQuery.data?.items),
    [compareQuery.data?.items, normalizedSymbols],
  );

  const derivedError = useMemo(() => {
    if (compareQuery.error) {
      return compareQuery.error.message || "组合分析加载失败";
    }
    if (items.length === 0) {
      return null;
    }
    const failedCount = items.filter((item) => item.failed).length;
    if (failedCount >= items.length) {
      return "行情接口暂时不可用，已展示本地占位数据。";
    }
    if (failedCount > 0) {
      return `部分标的加载失败（${failedCount}/${items.length}）。`;
    }
    return null;
  }, [compareQuery.error, items]);

  const summary = useMemo(() => {
    const total = items.length;
    const sectorSet = new Set(items.map((item) => item.sector || UNKNOWN_SECTOR));
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
      const sector = item.sector || UNKNOWN_SECTOR;
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
      .filter((item) => typeof item.percent === "number")
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
          radius: ["35%", "68%"],
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
      yAxis: {
        type: "value",
        axisLabel: {
          formatter: "{value}%",
        },
      },
      series: [
        {
          type: "bar",
          data: topMovers.map((item) => Number(item.percent || 0)),
          barMaxWidth: 36,
          itemStyle: {
            borderRadius: [8, 8, 0, 0],
          },
        },
      ],
      grid: { left: 40, right: 20, top: 30, bottom: 40 },
    };
  }, [topMovers]);

  const safePageSize = Math.max(1, pageSize);
  const totalPages = Math.max(1, Math.ceil(items.length / safePageSize));
  const currentPage = Math.min(page, totalPages);
  const pagedItems = useMemo(() => {
    const startIndex = (currentPage - 1) * safePageSize;
    return items.slice(startIndex, startIndex + safePageSize);
  }, [items, currentPage, safePageSize]);

  if (normalizedSymbols.length === 0) {
    return <div className="helper">{emptyText}</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <section className="card">
        <div className="card-title" style={{ marginBottom: 12 }}>
          {title}
        </div>
        <div className="toolbar">
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            标的数量
            <input className="input" type="number" value={normalizedSymbols.length} readOnly />
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            波动 TopN
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

      {compareQuery.isLoading && items.length === 0 ? (
        <div className="helper">组合分析加载中...</div>
      ) : (
        <>
          {derivedError ? (
            <div className="helper" style={{ color: "#b45309" }}>
              {derivedError}
            </div>
          ) : null}
          <section className="grid grid-3">
            <div className="card">
              <div className="helper">组合标的数</div>
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
              <div className="card-title">行业暴露（按数量）</div>
              {sectorPieOption ? (
                <ReactECharts option={sectorPieOption} style={{ height: 240 }} />
              ) : (
                <div className="helper">暂无行业数据</div>
              )}
            </div>
            <div className="card">
              <div className="card-title">涨跌幅波动 TopN</div>
              {moversBarOption ? (
                <ReactECharts option={moversBarOption} style={{ height: 240 }} />
              ) : (
                <div className="helper">暂无涨跌幅数据</div>
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
            <div className="card-title">组合标的明细</div>
            <div style={{ display: "grid", gap: 8 }}>
              {pagedItems.map((item) => (
                <div key={item.symbol} style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                  <span>
                    {item.symbol}
                    {item.name ? ` · ${item.name}` : ""}
                    {item.sector ? ` · ${item.sector}` : ""}
                  </span>
                  <span style={{ fontWeight: 600 }}>
                    {item.current === null ? "--" : formatNumber(item.current)} ·{" "}
                    {item.percent === null ? "--" : formatPercent(item.percent / 100)}
                  </span>
                </div>
              ))}
            </div>
            <div className="stock-pagination">
              <div className="helper">{`第 ${currentPage} / ${totalPages} 页`}</div>
              <div className="stock-pagination-actions">
                <button
                  type="button"
                  className="stock-page-button"
                  disabled={currentPage <= 1}
                  onClick={() => setPage((prev) => Math.max(1, prev - 1))}
                >
                  上一页
                </button>
                <button
                  type="button"
                  className="stock-page-button"
                  disabled={currentPage >= totalPages}
                  onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
                >
                  下一页
                </button>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
