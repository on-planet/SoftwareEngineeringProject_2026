import React, { useEffect, useMemo, useState } from "react";

import { getHeatmap } from "../services/api";
import { formatNumber, formatSigned } from "../utils/format";

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

export function Heatmap({
  asOf,
  market: initialMarket,
  minChange,
  maxChange,
}: {
  asOf?: string;
  market?: string;
  minChange?: number;
  maxChange?: number;
}) {
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
    setLoading(true);
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
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            市场
            <select
              value={market}
              onChange={(event) => {
                setMarket(event.target.value);
                setPage(1);
              }}
              style={{ padding: "4px 8px" }}
            >
              <option value="">全部市场</option>
              <option value="A">A股</option>
              <option value="HK">港股</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            排序
            <select
              value={sort}
              onChange={(event) => {
                setSort(event.target.value as SortOrder);
                setPage(1);
              }}
              style={{ padding: "4px 8px" }}
            >
              <option value="desc">降序</option>
              <option value="asc">升序</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            每页
            <select
              value={limit}
              onChange={(event) => {
                setLimit(Number(event.target.value) || 24);
                setPage(1);
              }}
              style={{ padding: "4px 8px" }}
            >
              <option value={12}>12</option>
              <option value={24}>24</option>
              <option value={48}>48</option>
            </select>
          </label>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#4a5568" }}>
          <button type="button" onClick={handlePrev} disabled={page <= 1}>
            上一页
          </button>
          <span>
            第 {page} / {maxPage} 页 · 共 {total} 条
          </span>
          <button type="button" onClick={handleNext} disabled={page >= maxPage}>
            下一页
          </button>
        </div>
      </div>
      {loading ? (
        <div>热力图加载中...</div>
      ) : error ? (
        <div>热力图加载失败：{error}</div>
      ) : items.length === 0 ? (
        <div>暂无热力图数据</div>
      ) : (
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
          {items.map((item) => {
            const color = item.avg_change >= 0 ? "#fed7d7" : "#c6f6d5";
            return (
              <div
                key={item.sector}
                style={{
                  border: "1px solid #e2e8f0",
                  borderRadius: 8,
                  padding: 12,
                  background: color,
                }}
              >
                <div style={{ fontWeight: 600 }}>{item.sector}</div>
                <div style={{ marginTop: 6, fontSize: 12, color: "#4a5568" }}>
                  均价 {formatNumber(item.avg_close)}
                </div>
                <div style={{ marginTop: 4, fontSize: 12 }}>
                  变动 {formatSigned(item.avg_change)}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
