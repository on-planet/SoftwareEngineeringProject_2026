import React, { useEffect, useState } from "react";

import { getSectorExposure } from "../services/api";
import { formatNumber, formatPercent } from "../utils/format";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";

type SectorItem = {
  sector: string;
  value: number;
  weight: number;
  symbol_count?: number;
};

type SectorResponse = {
  market: string | null;
  as_of?: string | null;
  basis: string;
  total_value: number;
  coverage: number;
  unknown_weight: number;
  items: SectorItem[];
};

type SortOrder = "asc" | "desc";

const SECTOR_EXPOSURE_CACHE_TTL_MS = 10 * 60 * 1000;

function buildSectorExposureCacheKey(market: string, sort: SortOrder, limit: number) {
  return `sector-exposure:market=${market || "all"}:sort=${sort}:limit=${limit}:basis=market_value`;
}

export function SectorExposurePanel() {
  const [market, setMarket] = useState("");
  const [sort, setSort] = useState<SortOrder>("desc");
  const [limit, setLimit] = useState(24);
  const [response, setResponse] = useState<SectorResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const cacheKey = buildSectorExposureCacheKey(market, sort, limit);
    const cachedResponse = readPersistentCache<SectorResponse>(cacheKey, SECTOR_EXPOSURE_CACHE_TTL_MS);
    if (cachedResponse) {
      setResponse(cachedResponse);
      setLoading(false);
    } else {
      setLoading(true);
    }
    getSectorExposure({
      market: market || undefined,
      basis: "market_value",
      sort,
      limit,
    })
      .then((res) => {
        if (!active) return;
        const payload = res as SectorResponse;
        setResponse(payload);
        writePersistentCache(cacheKey, payload);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) return;
        setError(err.message || "行业暴露加载失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [market, sort, limit]);

  const items = response?.items ?? [];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            市场
            <select className="select" value={market} onChange={(event) => setMarket(event.target.value)}>
              <option value="">全部</option>
              <option value="A">A股</option>
              <option value="HK">港股</option>
              <option value="US">美股</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            排序
            <select className="select" value={sort} onChange={(event) => setSort(event.target.value as SortOrder)}>
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

      {response ? (
        <div className="grid grid-3">
          <div className="card">
            <div className="helper">口径</div>
            <div style={{ fontWeight: 700, marginTop: 4 }}>{response.basis}</div>
            {response.as_of ? <div className="helper" style={{ marginTop: 6 }}>日期 {response.as_of}</div> : null}
          </div>
          <div className="card">
            <div className="helper">覆盖率</div>
            <div style={{ fontWeight: 700, marginTop: 4 }}>{formatPercent(response.coverage)}</div>
          </div>
          <div className="card">
            <div className="helper">未分类占比</div>
            <div style={{ fontWeight: 700, marginTop: 4 }}>{formatPercent(response.unknown_weight)}</div>
          </div>
        </div>
      ) : null}

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
              <div className="helper">占比 {formatPercent(item.weight)}</div>
              <div style={{ marginTop: 6, fontWeight: 600 }}>暴露值 {formatNumber(item.value)}</div>
              <div className="helper" style={{ marginTop: 4 }}>
                股票数 {formatNumber(item.symbol_count ?? 0)}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
