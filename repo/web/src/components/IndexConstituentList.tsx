import Link from "next/link";
import React, { useEffect, useMemo, useState } from "react";

import { INDEX_CONSTITUENT_OPTIONS } from "../constants/indices";
import { getIndexConstituents } from "../services/api";
import { formatNumber, formatSigned } from "../utils/format";

const TEXT = {
  loadError: "\u6307\u6570\u6210\u5206\u80a1\u52a0\u8f7d\u5931\u8d25",
  pageUnit: "\u6761",
  listTitle: "\u6307\u6570\u6210\u5206\u80a1",
  totalPrefix: "\u5171",
  totalSuffix: "\u53ea",
  loading: "\u6210\u5206\u80a1\u52a0\u8f7d\u4e2d...",
  empty: "\u6682\u65e0\u6210\u5206\u80a1\u6570\u636e\u3002",
  weight: "\u6743\u91cd",
  weightUnknown: "\u6743\u91cd\u6682\u672a\u516c\u5f00",
  contribution: "\u8d21\u732e\u70b9\u6570",
  source: "\u6765\u6e90",
  coverageHint: "\u5f53\u524d\u4f18\u5148\u4f7f\u7528 pysnowball\uff0c\u4e0d\u53ef\u7528\u65f6\u56de\u9000\u5230 CSI \u516c\u5f00\u6743\u91cd\u6587\u4ef6\u3002",
  prevPage: "\u4e0a\u4e00\u9875",
  nextPage: "\u4e0b\u4e00\u9875",
  page: "\u7b2c",
  pageSuffix: "\u9875",
};

const DEFAULT_INDEX =
  INDEX_CONSTITUENT_OPTIONS.find((item) => item.symbol === "000300.SH")?.symbol ??
  INDEX_CONSTITUENT_OPTIONS[0]?.symbol ??
  "000300.SH";

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
        setError(err.message || TEXT.loadError);
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
          <option value={10}>{`10 ${TEXT.pageUnit}`}</option>
          <option value={20}>{`20 ${TEXT.pageUnit}`}</option>
          <option value={50}>{`50 ${TEXT.pageUnit}`}</option>
        </select>
      </div>

      <div className="helper">
        {currentIndex ? `${currentIndex.label}${TEXT.listTitle}` : TEXT.listTitle}
        {total ? ` | ${TEXT.totalPrefix} ${total} ${TEXT.totalSuffix}` : ""}
      </div>
      <div className="helper">{TEXT.coverageHint}</div>

      {loading ? <div className="helper">{TEXT.loading}</div> : null}
      {!loading && error ? <div className="helper">{`${TEXT.loadError}: ${error}`}</div> : null}
      {!loading && !error && items.length === 0 ? <div className="helper">{TEXT.empty}</div> : null}

      {!loading && !error && items.length > 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {items.map((item) => (
            <Link
              key={`${item.index_symbol}-${item.symbol}-${item.rank ?? 0}`}
              href={`/stock/${encodeURIComponent(item.symbol)}`}
              className="card"
            >
              <div className="card-title">
                {item.rank ? `${item.rank}. ` : ""}
                {item.name || item.symbol}
              </div>
              <div className="helper" style={{ marginTop: 6 }}>
                {item.symbol}
                {item.market ? ` | ${item.market}` : ""}
                {item.date ? ` | ${String(item.date).slice(0, 10)}` : ""}
              </div>
              <div className="helper" style={{ marginTop: 6 }}>
                {item.weight !== null && item.weight !== undefined
                  ? `${TEXT.weight} ${formatNumber(item.weight)}`
                  : TEXT.weightUnknown}
                {item.contribution_change !== null && item.contribution_change !== undefined
                  ? ` | ${TEXT.contribution} ${formatSigned(item.contribution_change)}`
                  : ""}
              </div>
              {item.source ? (
                <div className="helper" style={{ marginTop: 6 }}>
                  {`${TEXT.source}: ${item.source}`}
                </div>
              ) : null}
            </Link>
          ))}

          <div className="helper" style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <button
              type="button"
              onClick={() => setPage((value) => Math.max(1, value - 1))}
              disabled={page <= 1}
              className="input"
            >
              {TEXT.prevPage}
            </button>
            <span>{`${TEXT.page} ${page} / ${maxPage} ${TEXT.pageSuffix}`}</span>
            <button
              type="button"
              onClick={() => setPage((value) => Math.min(maxPage, value + 1))}
              disabled={page >= maxPage}
              className="input"
            >
              {TEXT.nextPage}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
