import React, { useEffect, useMemo, useState } from "react";

import { getSectorExposure } from "../services/api";
import { formatNumber } from "../utils/format";

type SectorItem = {
  sector: string;
  value: number;
  weight: number;
};

type SectorResponse = {
  market: string | null;
  items: SectorItem[];
};

type SortOrder = "asc" | "desc";

export function SectorExposurePanel() {
  const [market, setMarket] = useState("");
  const [sort, setSort] = useState<SortOrder>("desc");
  const [limit, setLimit] = useState(24);
  const [items, setItems] = useState<SectorItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getSectorExposure({
      market: market || undefined,
      sort,
      limit,
    })
      .then((res) => {
        if (!active) return;
        const data = res as SectorResponse;
        setItems(data.items ?? []);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) return;
        setError(err.message || "加载行业暴露失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [market, sort, limit]);

  const totalWeight = useMemo(() => items.reduce((sum, item) => sum + (item.weight || 0), 0), [items]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            市场
            <select
              className="select"
              value={market}
              onChange={(event) => setMarket(event.target.value)}
            >
              <option value="">全部</option>
              <option value="A">A股</option>
              <option value="HK">港股</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            排序
            <select
              className="select"
              value={sort}
              onChange={(event) => setSort(event.target.value as SortOrder)}
            >
              <option value="desc">降序</option>
              <option value="asc">升序</option>
            </select>
          </label>
        </div>
        <select className="select" value={limit} onChange={(event) => setLimit(Number(event.target.value) || 24)}>
          <option value={12}>12 条</option>
          <option value={24}>24 条</option>
          <option value={36}>36 条</option>
        </select>
      </div>
      {loading ? (
        <div className="helper">行业暴露加载中...</div>
      ) : error ? (
        <div className="helper">行业暴露加载失败：{error}</div>
      ) : items.length === 0 ? (
        <div className="helper">暂无行业暴露数据</div>
      ) : (
        <div className="grid grid-3">
          {items.map((item) => (
            <div key={item.sector} className="card">
              <div className="card-title">{item.sector}</div>
              <div className="helper">占比 {formatNumber(item.weight * 100)}%</div>
              <div style={{ marginTop: 6, fontWeight: 600 }}>市值 {formatNumber(item.value)}</div>
              {totalWeight > 0 ? (
                <div className="helper" style={{ marginTop: 4 }}>
                  权重 {formatNumber((item.weight / totalWeight) * 100)}%
                </div>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
