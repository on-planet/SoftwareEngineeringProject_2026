import Link from "next/link";
import React, { useEffect, useMemo, useState } from "react";

import { INDEX_CONSTITUENT_OPTIONS } from "../constants/indices";
import { ApiPage, getIndexConstituents } from "../services/api";
import { formatNumber, formatSigned } from "../utils/format";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";
import { VirtualTable } from "./virtual/VirtualTable";

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

type ConstituentPage = ApiPage<ConstituentItem>;

const INDEX_CONSTITUENTS_CACHE_TTL_MS = 10 * 60 * 1000;

function buildIndexConstituentsCacheKey(indexSymbol: string, limit: number, offset: number) {
  return `index-constituents:${indexSymbol}:limit=${limit}:offset=${offset}`;
}

export function IndexConstituentList() {
  const [indexSymbol, setIndexSymbol] = useState(DEFAULT_INDEX);
  const [limit, setLimit] = useState(100);
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
    const cacheKey = buildIndexConstituentsCacheKey(indexSymbol, limit, offset);
    const cachedPage = readPersistentCache<ConstituentPage>(cacheKey, INDEX_CONSTITUENTS_CACHE_TTL_MS);
    if (cachedPage) {
      setItems(cachedPage.items ?? []);
      setTotal(cachedPage.total ?? 0);
      setLoading(false);
    } else {
      setLoading(true);
    }
    getIndexConstituents(indexSymbol, { limit, offset })
      .then((res) => {
        if (!active) {
          return;
        }
        const pageData = res as ConstituentPage;
        setItems(pageData.items ?? []);
        setTotal(pageData.total ?? 0);
        writePersistentCache(cacheKey, pageData);
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
          <option value={50}>{`50 ${TEXT.pageUnit}`}</option>
          <option value={100}>{`100 ${TEXT.pageUnit}`}</option>
          <option value={200}>{`200 ${TEXT.pageUnit}`}</option>
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
          <VirtualTable
            rows={items}
            rowKey={(item) => `${item.index_symbol}-${item.symbol}-${item.rank ?? 0}`}
            height={520}
            rowHeight={52}
            columns={[
              {
                key: "name",
                header: TEXT.listTitle,
                width: "1.6fr",
                cell: (item) => (
                  <Link href={`/stock/${encodeURIComponent(item.symbol)}`} className="subtle-link">
                    {item.rank ? `${item.rank}. ` : ""}
                    {item.name || item.symbol}
                  </Link>
                ),
              },
              {
                key: "symbol",
                header: "Symbol",
                width: "1fr",
                cell: (item) => item.symbol,
              },
              {
                key: "market",
                header: "Market",
                width: 90,
                cell: (item) => item.market || "--",
              },
              {
                key: "date",
                header: "Date",
                width: 120,
                cell: (item) => (item.date ? String(item.date).slice(0, 10) : "--"),
              },
              {
                key: "weight",
                header: TEXT.weight,
                width: 110,
                align: "right",
                cell: (item) =>
                  item.weight !== null && item.weight !== undefined ? formatNumber(item.weight) : TEXT.weightUnknown,
              },
              {
                key: "contribution_change",
                header: TEXT.contribution,
                width: 120,
                align: "right",
                cell: (item) =>
                  item.contribution_change !== null && item.contribution_change !== undefined
                    ? formatSigned(item.contribution_change)
                    : "--",
              },
              {
                key: "source",
                header: TEXT.source,
                width: "1.2fr",
                cell: (item) => item.source || "--",
              },
            ]}
          />

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
