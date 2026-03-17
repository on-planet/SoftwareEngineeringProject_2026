import Link from "next/link";
import { useRouter } from "next/router";
import React, { useEffect, useMemo, useRef, useState } from "react";

import { getStocks } from "../services/api";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";
import { getPrimaryStockName, getSecondaryStockName } from "../utils/stockNames";

const FALLBACK_SECTOR_LABEL = "未分类";
const STOCK_LIST_CACHE_TTL_MS = 5 * 60 * 1000;
const PAGE_SIZE = 24;
const SEARCH_DEBOUNCE_MS = 300;

type MarketCode = "A" | "HK";

type StockItem = {
  symbol: string;
  name: string;
  market: string;
  sector: string;
};

type StockPage = {
  items: StockItem[];
  total: number;
  limit: number;
  offset: number;
};

function normalizeSector(value?: string | null) {
  const text = String(value ?? "").trim();
  if (!text || text.toLowerCase() === "unknown" || text === "未知" || text === "未分类") {
    return FALLBACK_SECTOR_LABEL;
  }
  return text;
}

function buildStockListCacheKey(market: MarketCode, keyword: string, page: number) {
  return `stocks:v3:${market}:keyword=${keyword || "none"}:page=${page}:limit=${PAGE_SIZE}:sort=asc`;
}

function pageWindow(currentPage: number, totalPages: number) {
  const pages: number[] = [];
  const start = Math.max(1, currentPage - 2);
  const end = Math.min(totalPages, currentPage + 2);
  for (let page = start; page <= end; page += 1) {
    pages.push(page);
  }
  return pages;
}

function formatCount(value: number | null) {
  if (value === null) {
    return "--";
  }
  return value.toLocaleString("zh-CN");
}

function Pagination({
  page,
  total,
  pageSize,
  onPageChange,
}: {
  page: number;
  total: number;
  pageSize: number;
  onPageChange: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const pages = pageWindow(page, totalPages);

  return (
    <div className="stock-pagination">
      <div className="helper">{`第 ${page} / ${totalPages} 页，共 ${total} 只`}</div>
      <div className="stock-pagination-actions">
        <button
          type="button"
          className="stock-page-button"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          上一页
        </button>
        {pages.map((item) => (
          <button
            key={item}
            type="button"
            className="stock-page-button"
            data-active={item === page}
            onClick={() => onPageChange(item)}
          >
            {item}
          </button>
        ))}
        <button
          type="button"
          className="stock-page-button"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
        >
          下一页
        </button>
      </div>
    </div>
  );
}

function MarketSection({
  market,
  keyword,
  onTotalChange,
}: {
  market: MarketCode;
  keyword: string;
  onTotalChange?: (total: number | null) => void;
}) {
  const router = useRouter();
  const onTotalChangeRef = useRef(onTotalChange);
  const [items, setItems] = useState<StockItem[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    onTotalChangeRef.current = onTotalChange;
  }, [onTotalChange]);

  useEffect(() => {
    setPage(1);
  }, [keyword, market]);

  useEffect(() => {
    let active = true;
    const cacheKey = buildStockListCacheKey(market, keyword, page);
    const cachedPage = readPersistentCache<StockPage>(cacheKey, STOCK_LIST_CACHE_TTL_MS);
    const prefetchPage = (targetPage: number, knownTotal: number) => {
      const totalPages = Math.max(1, Math.ceil(knownTotal / PAGE_SIZE));
      if (targetPage < 1 || targetPage > totalPages) {
        return;
      }
      const targetKey = buildStockListCacheKey(market, keyword, targetPage);
      if (readPersistentCache<StockPage>(targetKey, STOCK_LIST_CACHE_TTL_MS)) {
        return;
      }
      void getStocks({
        market,
        keyword: keyword || undefined,
        sort: "asc",
        limit: PAGE_SIZE,
        offset: (targetPage - 1) * PAGE_SIZE,
      })
        .then((res) => {
          writePersistentCache(targetKey, res as StockPage);
        })
        .catch(() => {});
    };

    if (cachedPage) {
      setItems(cachedPage.items ?? []);
      setTotal(Number(cachedPage.total ?? 0));
      onTotalChangeRef.current?.(Number(cachedPage.total ?? 0));
      setLoading(false);
      prefetchPage(page + 1, Number(cachedPage.total ?? 0));
      return () => {
        active = false;
      };
    }
    setLoading(true);

    getStocks({
      market,
      keyword: keyword || undefined,
      sort: "asc",
      limit: PAGE_SIZE,
      offset: (page - 1) * PAGE_SIZE,
    })
      .then((res) => {
        if (!active) {
          return;
        }
        const payload = res as StockPage;
        const nextTotal = Number(payload.total ?? 0);
        setItems(payload.items ?? []);
        setTotal(nextTotal);
        onTotalChangeRef.current?.(nextTotal);
        writePersistentCache(cacheKey, payload);
        prefetchPage(page + 1, nextTotal);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        if (!cachedPage) {
          setItems([]);
          setTotal(0);
          onTotalChangeRef.current?.(0);
        }
        setError(err.message || "股票列表加载失败");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [keyword, market, page]);

  const marketLabel = market === "A" ? "A 股股票池" : "港股股票池";
  const marketChip = market === "A" ? "A 股" : "港股";
  const totalCount = total ?? 0;
  const rangeStart = totalCount === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(page * PAGE_SIZE, totalCount);
  const handleOpenStock = (event: React.MouseEvent<HTMLAnchorElement>, symbol: string) => {
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey ||
      event.currentTarget.target === "_blank"
    ) {
      return;
    }
    event.preventDefault();
    const href = `/stock/${encodeURIComponent(symbol)}`;
    let fallbackTimer: number | null = null;
    if (typeof window !== "undefined") {
      fallbackTimer = window.setTimeout(() => {
        window.location.assign(href);
      }, 1200);
    }
    void router
      .push(href)
      .then((ok) => {
        if (typeof window !== "undefined" && fallbackTimer !== null) {
          window.clearTimeout(fallbackTimer);
        }
        if (!ok && typeof window !== "undefined") {
          window.location.assign(href);
        }
      })
      .catch(() => {
        if (typeof window !== "undefined" && fallbackTimer !== null) {
          window.clearTimeout(fallbackTimer);
        }
        if (typeof window !== "undefined") {
          window.location.assign(href);
        }
      });
  };

  return (
    <section className="card stock-market-shell">
      <div className="section-headline">
        <div>
          <h2 className="section-title" style={{ marginBottom: 4 }}>
            {marketLabel}
          </h2>
          <div className="helper">{`当前展示 ${rangeStart}-${rangeEnd} / ${totalCount}`}</div>
        </div>
        <div className="stock-market-chip">{marketChip}</div>
      </div>

      {loading ? <div className="helper">股票列表加载中...</div> : null}
      {!loading && error ? <div className="helper">{`股票列表加载失败：${error}`}</div> : null}
      {!loading && !error && items.length === 0 ? <div className="helper">当前筛选条件下没有股票。</div> : null}

      {items.length > 0 ? (
        <>
          <div className="stock-grid">
            {items.map((item) => {
              const primaryName = getPrimaryStockName(item.symbol, item.name);
              const secondaryName = getSecondaryStockName(item.symbol, item.name);
              return (
                <Link
                  key={item.symbol}
                  href={`/stock/${encodeURIComponent(item.symbol)}`}
                  prefetch={false}
                  onClick={(event) => handleOpenStock(event, item.symbol)}
                  className="stock-card"
                >
                  <div className="stock-card-title">{primaryName}</div>
                  {secondaryName ? <div className="helper">{secondaryName}</div> : null}
                  <div className="helper">{item.symbol}</div>
                  <div className="stock-card-meta">
                    <span>{item.market}</span>
                    <span>{normalizeSector(item.sector)}</span>
                  </div>
                </Link>
              );
            })}
          </div>

          <Pagination page={page} total={totalCount} pageSize={PAGE_SIZE} onPageChange={setPage} />
        </>
      ) : null}
    </section>
  );
}

export default function StocksPage() {
  const [keyword, setKeyword] = useState("");
  const [debouncedKeyword, setDebouncedKeyword] = useState("");
  const [totals, setTotals] = useState<Record<MarketCode, number | null>>({
    A: null,
    HK: null,
  });

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedKeyword(keyword.trim());
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [keyword]);

  const keywordLabel = useMemo(() => debouncedKeyword.trim(), [debouncedKeyword]);
  const totalCount =
    (typeof totals.A === "number" ? totals.A : 0) + (typeof totals.HK === "number" ? totals.HK : 0);

  return (
    <div className="page">
      <section className="card stock-pool-hero">
        <div className="page-header">
          <div>
            <h1 className="page-title">股票池</h1>
            <p className="helper" style={{ marginTop: 8, maxWidth: 760 }}>
              汇总 A 股与港股股票池，按页展示全部可用标的。列表优先读取本地缓存与已预热的中文名、行业分类，
              支持按代码、名称和行业搜索。
            </p>
          </div>
          <div className="toolbar">
            <input
              className="input"
              type="text"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="按代码、名称或行业搜索"
            />
          </div>
        </div>

        <div className="hero-grid">
          <div className="hero-metric">
            <div className="helper">A 股总数</div>
            <div className="hero-metric-value">{formatCount(totals.A)}</div>
            <div className="helper">独立分页展示，优先读取本地股票池缓存</div>
          </div>
          <div className="hero-metric">
            <div className="helper">港股总数</div>
            <div className="hero-metric-value">{formatCount(totals.HK)}</div>
            <div className="helper">支持中文名、代码与行业联合筛选</div>
          </div>
          <div className="hero-metric">
            <div className="helper">当前筛选</div>
            <div className="hero-metric-value">{keywordLabel || "全部股票"}</div>
            <div className="helper">{`总计 ${formatCount(totalCount)} 只，每页 ${PAGE_SIZE} 只，输入防抖 300ms`}</div>
          </div>
        </div>

        <div className="stock-pool-summary">
          <div className="stock-summary-chip">A 股与港股全量分页展示</div>
          <div className="stock-summary-chip">{keywordLabel ? `当前筛选：${keywordLabel}` : "当前筛选：全部股票"}</div>
          <div className="stock-summary-chip">每页 24 只</div>
        </div>
      </section>

      <MarketSection
        market="A"
        keyword={debouncedKeyword}
        onTotalChange={(value) => setTotals((prev) => ({ ...prev, A: value }))}
      />
      <MarketSection
        market="HK"
        keyword={debouncedKeyword}
        onTotalChange={(value) => setTotals((prev) => ({ ...prev, HK: value }))}
      />
    </div>
  );
}
