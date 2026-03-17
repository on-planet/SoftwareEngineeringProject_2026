import React, { useEffect, useMemo, useState } from "react";

import { getHeatmap } from "../services/api";
import { formatNumber, formatSigned } from "../utils/format";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";

type HeatmapItem = {
  sector: string;
  avg_close: number;
  avg_change: number;
};

type HeatmapPage = {
  items: HeatmapItem[];
  total: number;
  limit: number;
  offset: number;
};

type SortOrder = "asc" | "desc";

type HeatmapProps = {
  asOf?: string;
  market?: string;
  minChange?: number;
  maxChange?: number;
  showMarketSelector?: boolean;
};

const HEATMAP_CACHE_TTL_MS = 5 * 60 * 1000;

function buildHeatmapCacheKey(params: {
  asOf?: string;
  market: string;
  minChange?: number;
  maxChange?: number;
  sort: SortOrder;
  limit: number;
  offset: number;
}) {
  return [
    "heatmap",
    `asOf=${params.asOf || "latest"}`,
    `market=${params.market || "all"}`,
    `minChange=${params.minChange ?? "none"}`,
    `maxChange=${params.maxChange ?? "none"}`,
    `sort=${params.sort}`,
    `limit=${params.limit}`,
    `offset=${params.offset}`,
  ].join(":");
}

function displaySectorName(value: string) {
  return value === "Unknown" ? "未知" : value;
}

export function Heatmap({
  asOf,
  market: initialMarket,
  minChange,
  maxChange,
  showMarketSelector = initialMarket === undefined,
}: HeatmapProps) {
  const [market, setMarket] = useState(initialMarket ?? "");
  const [sort, setSort] = useState<SortOrder>("desc");
  const [limit, setLimit] = useState(24);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [items, setItems] = useState<HeatmapItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (initialMarket !== undefined) {
      setMarket(initialMarket);
      setPage(1);
    }
  }, [initialMarket]);

  const offset = useMemo(() => (page - 1) * limit, [page, limit]);
  const maxPage = useMemo(() => Math.max(1, Math.ceil(total / limit)), [total, limit]);

  useEffect(() => {
    let active = true;
    const cacheKey = buildHeatmapCacheKey({
      asOf,
      market,
      minChange,
      maxChange,
      sort,
      limit,
      offset,
    });
    const cachedPage = readPersistentCache<HeatmapPage>(cacheKey, HEATMAP_CACHE_TTL_MS);
    if (cachedPage) {
      setItems(cachedPage.items ?? []);
      setTotal(cachedPage.total ?? 0);
      setLoading(false);
    } else {
      setLoading(true);
    }

    getHeatmap({
      as_of: asOf,
      market: market || undefined,
      min_change: minChange,
      max_change: maxChange,
      sort,
      limit,
      offset,
    })
      .then((res) => {
        if (!active) {
          return;
        }
        const pageData = res as HeatmapPage;
        setItems(pageData.items ?? []);
        setTotal(pageData.total ?? 0);
        writePersistentCache(cacheKey, pageData);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setError(err.message || "加载热力图失败");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [asOf, market, minChange, maxChange, sort, limit, offset]);

  const handlePrev = () => setPage((prev) => Math.max(1, prev - 1));
  const handleNext = () => setPage((prev) => Math.min(maxPage, prev + 1));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {showMarketSelector ? (
            <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
              市场
              <select
                className="select"
                value={market}
                onChange={(event) => {
                  setMarket(event.target.value);
                  setPage(1);
                }}
              >
                <option value="">全部市场</option>
                <option value="A">A股</option>
                <option value="HK">港股</option>
              </select>
            </label>
          ) : null}
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            排序
            <select
              className="select"
              value={sort}
              onChange={(event) => {
                setSort(event.target.value as SortOrder);
                setPage(1);
              }}
            >
              <option value="desc">降序</option>
              <option value="asc">升序</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            每页
            <select
              className="select"
              value={limit}
              onChange={(event) => {
                setLimit(Number(event.target.value) || 24);
                setPage(1);
              }}
            >
              <option value={12}>12</option>
              <option value={24}>24</option>
              <option value={48}>48</option>
            </select>
          </label>
        </div>
        <div className="helper" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <button type="button" onClick={handlePrev} disabled={page <= 1} className="input">
            上一页
          </button>
          <span>
            第 {page} / {maxPage} 页 · 共 {total} 条
          </span>
          <button type="button" onClick={handleNext} disabled={page >= maxPage} className="input">
            下一页
          </button>
        </div>
      </div>
      {loading ? (
        <div className="helper">热力图加载中...</div>
      ) : error ? (
        <div className="helper">热力图加载失败：{error}</div>
      ) : items.length === 0 ? (
        <div className="helper">暂无热力图数据</div>
      ) : (
        <div className="grid grid-3">
          {items.map((item) => {
            const bgColor =
              item.avg_change >= 0 ? "rgba(248, 113, 113, 0.2)" : "rgba(52, 211, 153, 0.2)";
            return (
              <div key={item.sector} className="card" style={{ background: bgColor }}>
                <div className="card-title">{displaySectorName(item.sector)}</div>
                <div className="helper">均价 {formatNumber(item.avg_close)}</div>
                <div style={{ marginTop: 4, fontWeight: 600 }}>变动 {formatSigned(item.avg_change)}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
