import React, { useEffect, useMemo, useState } from "react";

import { getIndexConstituents } from "../services/api";

const DEFAULT_INDEX = "000001.SH";

type ConstituentItem = {
  index_symbol: string;
  symbol: string;
  date: string;
  weight: number;
};

type ConstituentPage = {
  items: ConstituentItem[];
  total: number;
  limit: number;
  offset: number;
};

export function IndexConstituentList() {
  const [indexSymbol, setIndexSymbol] = useState(DEFAULT_INDEX);
  const [limit, setLimit] = useState(20);
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<ConstituentItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const offset = useMemo(() => (page - 1) * limit, [page, limit]);
  const maxPage = useMemo(() => Math.max(1, Math.ceil(total / limit)), [total, limit]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getIndexConstituents(indexSymbol, { limit, offset })
      .then((res) => {
        if (!active) return;
        const pageData = res as ConstituentPage;
        setItems(pageData.items ?? []);
        setTotal(pageData.total ?? 0);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) return;
        setError(err.message || "加载指数成分失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [indexSymbol, limit, offset]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input
            className="input"
            value={indexSymbol}
            onChange={(event) => {
              setIndexSymbol(event.target.value.trim().toUpperCase());
              setPage(1);
            }}
            placeholder="指数代码"
            style={{ width: 160 }}
          />
        </div>
        <select className="select" value={limit} onChange={(event) => {
          setLimit(Number(event.target.value) || 20);
          setPage(1);
        }}>
          <option value={10}>10 条</option>
          <option value={20}>20 条</option>
          <option value={30}>30 条</option>
        </select>
      </div>
      {loading ? (
        <div className="helper">成分股加载中...</div>
      ) : error ? (
        <div className="helper">成分股加载失败：{error}</div>
      ) : items.length === 0 ? (
        <div className="helper">暂无成分股数据</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div className="helper">共 {total} 条</div>
          {items.map((item) => (
            <div key={`${item.index_symbol}-${item.symbol}-${item.date}`} className="card">
              <div className="card-title">{item.symbol}</div>
              <div className="helper" style={{ marginTop: 6 }}>{item.index_symbol} · {item.date}</div>
              <div style={{ marginTop: 6, fontSize: 12 }}>权重 {item.weight}</div>
            </div>
          ))}
          <div className="helper" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1} className="input">
              上一页
            </button>
            <span>第 {page} / {maxPage} 页</span>
            <button type="button" onClick={() => setPage((p) => Math.min(maxPage, p + 1))} disabled={page >= maxPage} className="input">
              下一页
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
