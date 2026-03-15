import Link from "next/link";
import React, { useEffect, useMemo, useState } from "react";

import { INDEX_CONSTITUENT_OPTIONS } from "../constants/indices";
import { getIndexConstituents } from "../services/api";
import { formatNumber, formatSigned } from "../utils/format";

const DEFAULT_INDEX = INDEX_CONSTITUENT_OPTIONS[0]?.symbol ?? "HKHSI";

type ConstituentItem = {
  index_symbol: string;
  symbol: string;
  date: string;
  weight?: number | null;
  name?: string | null;
  market?: string | null;
  rank?: number | null;
  contribution_change?: number | null;
  source?: string | null;
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
  const currentIndex = useMemo(
    () => INDEX_CONSTITUENT_OPTIONS.find((item) => item.symbol === indexSymbol),
    [indexSymbol],
  );

  useEffect(() => {
    let active = true;
    setLoading(true);
    getIndexConstituents(indexSymbol, { limit, offset })
      .then((res) => {
        if (!active) {
          return;
        }
        const pageData = res as ConstituentPage;
        setItems(pageData.items ?? []);
        setTotal(pageData.total ?? 0);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setError(err.message || "指数成分股加载失败");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [indexSymbol, limit, offset]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <select
            className="select"
            value={indexSymbol}
            onChange={(event) => {
              setIndexSymbol(event.target.value);
              setPage(1);
            }}
          >
            {INDEX_CONSTITUENT_OPTIONS.map((item) => (
              <option key={item.symbol} value={item.symbol}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
        <select
          className="select"
          value={limit}
          onChange={(event) => {
            setLimit(Number(event.target.value) || 20);
            setPage(1);
          }}
        >
          <option value={10}>10 条</option>
          <option value={20}>20 条</option>
          <option value={50}>50 条</option>
        </select>
      </div>

      <div className="helper">
        {currentIndex ? `${currentIndex.label}成分股` : "指数成分股"}
        {total ? ` · 共 ${total} 只` : ""}
      </div>

      {loading ? <div className="helper">成分股加载中...</div> : null}
      {!loading && error ? <div className="helper">成分股加载失败：{error}</div> : null}
      {!loading && !error && items.length === 0 ? <div className="helper">暂无成分股数据。</div> : null}

      {!loading && !error && items.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {items.map((item) => (
            <Link key={`${item.index_symbol}-${item.symbol}-${item.rank ?? 0}`} href={`/stock/${encodeURIComponent(item.symbol)}`} className="card">
              <div className="card-title">
                {item.rank ? `${item.rank}. ` : ""}
                {item.name || item.symbol}
              </div>
              <div className="helper" style={{ marginTop: 6 }}>
                {item.symbol}
                {item.market ? ` · ${item.market}` : ""}
                {item.date ? ` · ${String(item.date).slice(0, 10)}` : ""}
              </div>
              <div className="helper" style={{ marginTop: 6 }}>
                {item.weight !== null && item.weight !== undefined ? `权重 ${formatNumber(item.weight)}` : "权重暂未公开"}
                {item.contribution_change !== null && item.contribution_change !== undefined
                  ? ` · 贡献点数 ${formatSigned(item.contribution_change)}`
                  : ""}
              </div>
              {item.source ? (
                <div className="helper" style={{ marginTop: 6 }}>
                  来源：{item.source}
                </div>
              ) : null}
            </Link>
          ))}

          <div className="helper" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button type="button" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1} className="input">
              上一页
            </button>
            <span>
              第 {page} / {maxPage} 页
            </span>
            <button
              type="button"
              onClick={() => setPage((value) => Math.min(maxPage, value + 1))}
              disabled={page >= maxPage}
              className="input"
            >
              下一页
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
