import Link from "next/link";
import { useRouter } from "next/router";
import React, { useEffect, useMemo, useState } from "react";

import { useApiQuery } from "../hooks/useApiQuery";
import { useAuth } from "../providers/AuthProvider";
import {
  buildMyWorkspaceQueryKey,
  createMyStockFilter,
  createMyStockPool,
  deleteMyStockFilter,
  deleteMyStockPool,
  getUserScopedQueryOptions,
  getMyWorkspaceQueryOptions,
  getCompareStocks,
  getMyWorkspace,
  getStocks,
  runApiQuery,
  StockCompareItem,
  UserStockFilterItem,
  UserStockPoolItem,
} from "../services/api";
import { getPrimaryStockName, getSecondaryStockName } from "../utils/stockNames";
import { addWatchTarget, readWatchTargets } from "../utils/watchTargets";
import { PortfolioAnalysisPanel } from "./PortfolioAnalysisPanel";

import styles from "./StockPoolMarketPage.module.css";

const FALLBACK_SECTOR_LABEL = "未分类";
const STOCK_LIST_CACHE_TTL_MS = 5 * 60 * 1000;
const PAGE_SIZE = 24;
const SEARCH_DEBOUNCE_MS = 280;

export type MarketCode = "A" | "HK";

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

function normalizeSymbol(value?: string | null) {
  return String(value || "").trim().toUpperCase();
}

function normalizeSector(value?: string | null) {
  const text = String(value ?? "").trim();
  if (!text || text.toLowerCase() === "unknown" || text === "未知" || text === "未分类") {
    return FALLBACK_SECTOR_LABEL;
  }
  return text;
}

function dedupeSymbols(values: string[]) {
  const unique = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const symbol = normalizeSymbol(value);
    if (!symbol || unique.has(symbol)) {
      continue;
    }
    unique.add(symbol);
    result.push(symbol);
  }
  return result;
}

function buildStockListCacheKey(market: MarketCode, keyword: string, sector: string, page: number) {
  return `stocks:v5:${market}:keyword=${keyword || "none"}:sector=${sector || "none"}:page=${page}:limit=${PAGE_SIZE}:sort=asc`;
}

function getStockListQueryOptions(cacheKey: string) {
  return {
    staleTimeMs: 30_000,
    cacheTimeMs: STOCK_LIST_CACHE_TTL_MS,
    persist: {
      key: cacheKey,
      maxAgeMs: STOCK_LIST_CACHE_TTL_MS,
    },
  };
}

function fetchStockPage(market: MarketCode, keyword: string, sector: string, page: number) {
  return getStocks({
    market,
    keyword: keyword || undefined,
    sector: sector || undefined,
    sort: "asc",
    limit: PAGE_SIZE,
    offset: (page - 1) * PAGE_SIZE,
  }) as Promise<StockPage>;
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

function WorkspaceCard({
  title,
  helper,
  children,
  kicker,
  tone,
}: {
  title: string;
  helper: string;
  children: React.ReactNode;
  kicker: string;
  tone?: "warm" | "cool" | "neutral";
}) {
  return (
    <section className={`card market-panel ${styles.workspaceCard}`} data-tone={tone}>
      <div className={styles.workspaceHeader}>
        <div>
          <div className="card-title">{title}</div>
          <div className="helper">{helper}</div>
        </div>
        <span className="kicker">{kicker}</span>
      </div>
      {children}
    </section>
  );
}

function ActivePoolSection({
  pool,
  compareItems,
  loading,
  error,
  onClose,
  onAddToWatch,
  addedCount,
}: {
  pool: UserStockPoolItem;
  compareItems: StockCompareItem[];
  loading: boolean;
  error: string | null;
  onClose: () => void;
  onAddToWatch: () => void;
  addedCount: number;
}) {
  return (
    <section className={`card market-panel ${styles.activePoolPanel}`} data-tone="cool">
      <div className={styles.workspaceHeader}>
        <div>
          <div className="card-title">{`自定义股票池 · ${pool.name}`}</div>
          <div className="helper">{`${pool.market} 市场 · ${pool.symbols.length} 个标的`}</div>
        </div>
        <div className={styles.workspaceItemActions}>
          <button type="button" className="primary-button" onClick={onAddToWatch}>
            {addedCount > 0 ? `已添加 ${addedCount} 个` : "添加到观察"}
          </button>
          <button type="button" className="stock-page-button" onClick={onClose}>
            关闭
          </button>
        </div>
      </div>

      {loading ? <div className="helper">股票池详情加载中...</div> : null}
      {!loading && error ? (
        <div className="helper" style={{ color: "var(--finance-rise)" }}>
          {error}
        </div>
      ) : null}

      {!loading && !error ? (
        <>
          <div className={styles.activePoolGrid}>
            {compareItems.map((item) => (
              <div key={item.symbol} className={styles.activePoolCard}>
                <div style={{ fontWeight: 700 }}>{item.name || item.symbol}</div>
                <div className="helper">{item.symbol}</div>
                <div className={styles.activePoolMeta}>
                  <span>{item.market || pool.market}</span>
                  <span>{normalizeSector(item.sector)}</span>
                </div>
                <div style={{ fontWeight: 700, marginTop: 4 }}>
                  {typeof item.quote?.current === "number" ? item.quote.current.toFixed(2) : "--"}
                </div>
                <div className={typeof item.quote?.percent === "number" ? (item.quote.percent >= 0 ? "trend-up" : "trend-down") : "helper"}>
                  {typeof item.quote?.percent === "number" ? `${item.quote.percent.toFixed(2)}%` : item.error || "暂无行情"}
                </div>
              </div>
            ))}
          </div>
          <PortfolioAnalysisPanel
            symbols={pool.symbols}
            title={`${pool.name} 组合分析`}
            emptyText="当前股票池里还没有标的。"
            pageSize={12}
          />
        </>
      ) : null}
    </section>
  );
}

function MarketSection({
  market,
  keyword,
  sector,
  selectedSymbols,
  onToggleSymbol,
  onSelectPage,
  onClearPage,
  onTotalChange,
}: {
  market: MarketCode;
  keyword: string;
  sector: string;
  selectedSymbols: string[];
  onToggleSymbol: (symbol: string) => void;
  onSelectPage: (symbols: string[]) => void;
  onClearPage: (symbols: string[]) => void;
  onTotalChange?: (total: number | null) => void;
}) {
  const router = useRouter();
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [keyword, sector, market]);

  const cacheKey = useMemo(
    () => buildStockListCacheKey(market, keyword, sector, page),
    [keyword, market, page, sector],
  );
  const listQuery = useApiQuery<StockPage>(
    cacheKey,
    () => fetchStockPage(market, keyword, sector, page),
    getStockListQueryOptions(cacheKey),
  );
  const items = listQuery.data?.items ?? [];
  const total = typeof listQuery.data?.total === "number" ? Number(listQuery.data.total) : null;
  const loading = listQuery.isLoading;
  const error = listQuery.error?.message ?? null;

  useEffect(() => {
    if (!onTotalChange) {
      return;
    }
    if (typeof listQuery.data?.total === "number") {
      onTotalChange(Number(listQuery.data.total));
      return;
    }
    if (listQuery.error && !listQuery.data) {
      onTotalChange(0);
      return;
    }
    onTotalChange(null);
  }, [listQuery.data, listQuery.error, onTotalChange]);

  useEffect(() => {
    const knownTotal = Number(listQuery.data?.total ?? 0);
    if (!knownTotal) {
      return;
    }
    const totalPages = Math.max(1, Math.ceil(knownTotal / PAGE_SIZE));
    const targetPage = page + 1;
    if (targetPage < 1 || targetPage > totalPages) {
      return;
    }
    const targetKey = buildStockListCacheKey(market, keyword, sector, targetPage);
    void runApiQuery(
      targetKey,
      () => fetchStockPage(market, keyword, sector, targetPage),
      getStockListQueryOptions(targetKey),
    ).catch(() => undefined);
  }, [keyword, listQuery.data?.total, market, page, sector]);

  const marketLabel = market === "A" ? "A 股股票池" : "港股股票池";
  const totalCount = total ?? 0;
  const rangeStart = totalCount === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const rangeEnd = Math.min(page * PAGE_SIZE, totalCount);
  const pageSymbols = useMemo(() => items.map((item) => normalizeSymbol(item.symbol)), [items]);
  const selectedOnPage = pageSymbols.filter((item) => selectedSymbols.includes(item)).length;

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
      </div>

      <div className={`toolbar ${styles.selectionToolbar}`} style={{ marginBottom: 12 }}>
        <div className="helper">{`本页已选择 ${selectedOnPage} / ${pageSymbols.length}，全局已选择 ${selectedSymbols.length}`}</div>
        <div className={styles.selectionToolbarActions}>
          <button type="button" className="stock-page-button" onClick={() => onSelectPage(pageSymbols)} disabled={pageSymbols.length === 0}>
            选择本页
          </button>
          <button type="button" className="stock-page-button" onClick={() => onClearPage(pageSymbols)} disabled={selectedOnPage === 0}>
            清空本页
          </button>
        </div>
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
              const normalized = normalizeSymbol(item.symbol);
              const selected = selectedSymbols.includes(normalized);
              return (
                <div key={item.symbol} className={`stock-card ${styles.selectableCard}`} data-selected={selected}>
                  <div className={styles.cardSelectionRow}>
                    <label className={styles.cardSelection}>
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={() => onToggleSymbol(normalized)}
                      />
                      <span>加入自定义池</span>
                    </label>
                  </div>
                  <Link
                    href={`/stock/${encodeURIComponent(item.symbol)}`}
                    prefetch={false}
                    onClick={(event) => handleOpenStock(event, item.symbol)}
                    className={styles.stockLink}
                  >
                    <div className="stock-card-title">{primaryName}</div>
                    {secondaryName ? <div className="helper">{secondaryName}</div> : null}
                    <div className="helper">{item.symbol}</div>
                    <div className="stock-card-meta">
                      <span>{item.market}</span>
                      <span>{normalizeSector(item.sector)}</span>
                    </div>
                  </Link>
                </div>
              );
            })}
          </div>

          <Pagination page={page} total={totalCount} pageSize={PAGE_SIZE} onPageChange={setPage} />
        </>
      ) : null}
    </section>
  );
}

export function StockPoolMarketPage({ market }: { market: MarketCode }) {
  const [keyword, setKeyword] = useState("");
  const [debouncedKeyword, setDebouncedKeyword] = useState("");
  const [sector, setSector] = useState("");
  const [debouncedSector, setDebouncedSector] = useState("");
  const [total, setTotal] = useState<number | null>(null);
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>([]);
  const [poolName, setPoolName] = useState("");
  const [filterName, setFilterName] = useState("");
  const [workspaceMessage, setWorkspaceMessage] = useState<string | null>(null);
  const [activePoolId, setActivePoolId] = useState<number | null>(null);
  const [addedToWatchCount, setAddedToWatchCount] = useState(0);
  const { isAuthenticated, token, isLoading: authLoading } = useAuth();

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedKeyword(keyword.trim());
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [keyword]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedSector(sector.trim());
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
  }, [sector]);
  const workspaceQueryKey = useMemo(
    () => (isAuthenticated && token ? buildMyWorkspaceQueryKey(token) : null),
    [isAuthenticated, token],
  );

  const workspaceQuery = useApiQuery(
    workspaceQueryKey,
    () => getMyWorkspace(token as string),
    workspaceQueryKey ? getMyWorkspaceQueryOptions(workspaceQueryKey) : getUserScopedQueryOptions("workspace"),
  );

  const savedPools = useMemo(
    () => (workspaceQuery.data?.pools || []).filter((item) => item.market === market),
    [workspaceQuery.data?.pools, market],
  );
  const savedFilters = useMemo(
    () => (workspaceQuery.data?.filters || []).filter((item) => item.market === market),
    [workspaceQuery.data?.filters, market],
  );
  const activePool = useMemo(
    () => savedPools.find((item) => item.id === activePoolId) || null,
    [activePoolId, savedPools],
  );

  useEffect(() => {
    if (activePoolId !== null && !savedPools.some((item) => item.id === activePoolId)) {
      setActivePoolId(null);
    }
  }, [activePoolId, savedPools]);

  const activePoolQuery = useApiQuery(
    activePool ? ["stock-compare", "saved-pool", activePool.id, ...activePool.symbols] : null,
    () =>
      getCompareStocks(
        {
          symbols: activePool?.symbols || [],
          prefer_live: true,
        },
        { retry: 1 },
      ),
    {
      staleTimeMs: 60_000,
      cacheTimeMs: 5 * 60_000,
    },
  );

  const marketTitle = market === "A" ? "A 股股票池" : "港股股票池";
  const marketSummary = market === "A" ? "A 股市场工作台" : "港股市场工作台";
  const keywordLabel = useMemo(() => debouncedKeyword.trim(), [debouncedKeyword]);
  const sectorLabel = useMemo(() => debouncedSector.trim(), [debouncedSector]);

  const handleToggleSymbol = (symbol: string) => {
    setSelectedSymbols((prev) => {
      if (prev.includes(symbol)) {
        return prev.filter((item) => item !== symbol);
      }
      return [...prev, symbol];
    });
  };

  const handleSelectPage = (symbols: string[]) => {
    setSelectedSymbols((prev) => dedupeSymbols([...prev, ...symbols]));
  };

  const handleClearPage = (symbols: string[]) => {
    setSelectedSymbols((prev) => prev.filter((item) => !symbols.includes(item)));
  };

  const handleCreatePool = async () => {
    if (!token || !isAuthenticated) {
      setWorkspaceMessage("登录后才能保存自定义股票池。");
      return;
    }
    const name = poolName.trim();
    const symbols = dedupeSymbols(selectedSymbols);
    if (!name) {
      setWorkspaceMessage("请输入股票池名称。");
      return;
    }
    if (symbols.length === 0) {
      setWorkspaceMessage("请先从列表里选择至少一个标的。");
      return;
    }
    try {
      await createMyStockPool(token, { name, market, symbols });
      setPoolName("");
      setWorkspaceMessage(null);
      await workspaceQuery.refetch();
    } catch (error) {
      setWorkspaceMessage(error instanceof Error ? error.message : "保存股票池失败");
    }
  };

  const handleCreateFilter = async () => {
    if (!token || !isAuthenticated) {
      setWorkspaceMessage("登录后才能保存筛选器。");
      return;
    }
    const name = filterName.trim();
    if (!name) {
      setWorkspaceMessage("请输入筛选器名称。");
      return;
    }
    try {
      await createMyStockFilter(token, {
        name,
        market,
        keyword: keyword.trim(),
        sector: sector.trim(),
        sort: "asc",
      });
      setFilterName("");
      setWorkspaceMessage(null);
      await workspaceQuery.refetch();
    } catch (error) {
      setWorkspaceMessage(error instanceof Error ? error.message : "保存筛选器失败");
    }
  };

  const handleDeletePool = async (poolId: number) => {
    if (!token || !isAuthenticated) {
      return;
    }
    try {
      await deleteMyStockPool(token, poolId);
      if (activePoolId === poolId) {
        setActivePoolId(null);
      }
      setWorkspaceMessage(null);
      await workspaceQuery.refetch();
    } catch (error) {
      setWorkspaceMessage(error instanceof Error ? error.message : "删除股票池失败");
    }
  };

  const handleDeleteFilter = async (filterId: number) => {
    if (!token || !isAuthenticated) {
      return;
    }
    try {
      await deleteMyStockFilter(token, filterId);
      setWorkspaceMessage(null);
      await workspaceQuery.refetch();
    } catch (error) {
      setWorkspaceMessage(error instanceof Error ? error.message : "删除筛选器失败");
    }
  };

  const handleApplyFilter = (item: UserStockFilterItem) => {
    setKeyword(item.keyword || "");
    setSector(item.sector || "");
    setActivePoolId(null);
    setWorkspaceMessage(null);
  };

  const activePoolError = activePoolQuery.error?.message || null;

  const handleAddPoolToWatch = (symbols: string[]) => {
    const currentWatch = readWatchTargets();
    let added = 0;
    for (const symbol of symbols) {
      const normalized = symbol.trim().toUpperCase();
      if (normalized && !currentWatch.includes(normalized)) {
        addWatchTarget(normalized);
        added += 1;
      }
    }
    setAddedToWatchCount(added);
    setWorkspaceMessage(`已成功添加 ${added} 个标的到观察列表`);
    setTimeout(() => setAddedToWatchCount(0), 3000);
  };

  return (
    <div className="page">
      <section className="card stock-pool-hero">
        <div className="page-header">
          <div>
            <span className="kicker">市场筛选器</span>
            <h1 className="page-title">{marketTitle}</h1>
            <p className="helper" style={{ marginTop: 8, maxWidth: 760 }}>
              股票池按市场拆分，支持保存筛选器和自定义股票池；组合分析与股票池详情共用同一套批量股票概览接口。
            </p>
          </div>
        </div>

        <div className="stock-market-tabs">
          <Link href="/stocks/a" className="stock-market-tab" data-active={market === "A"}>
            A股
          </Link>
          <Link href="/stocks/hk" className="stock-market-tab" data-active={market === "HK"}>
            港股
          </Link>
        </div>

        <div className="stock-filter-grid">
          <label className="stock-filter-field">
            <span className="stock-filter-label">关键词搜索</span>
            <input
              className="input"
              type="text"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="按代码或名称搜索"
            />
          </label>
          <label className="stock-filter-field">
            <span className="stock-filter-label">类别搜索</span>
            <input
              className="input"
              type="text"
              value={sector}
              onChange={(event) => setSector(event.target.value)}
              placeholder="按行业类别搜索，例如：银行、新能源、互联网"
            />
          </label>
        </div>

        <div className="hero-grid">
          <div className="hero-metric">
            <div className="helper">当前分页面</div>
            <div className="hero-metric-value">{marketSummary}</div>
            <div className="helper">筛选器和自定义池会按市场分别保存</div>
          </div>
          <div className="hero-metric">
            <div className="helper">当前总数</div>
            <div className="hero-metric-value">{formatCount(total)}</div>
            <div className="helper">每页 24 只，自动预取下一页缓存</div>
          </div>
          <div className="hero-metric">
            <div className="helper">筛选条件</div>
            <div className="hero-metric-value">{keywordLabel || sectorLabel ? "已筛选" : "全部股票"}</div>
            <div className="helper">{`关键词：${keywordLabel || "无"} · 类别：${sectorLabel || "无"}`}</div>
          </div>
        </div>
      </section>

      <section className={styles.workspaceGrid}>
        <WorkspaceCard
          title="自定义股票池"
          helper="从当前列表批量选择标的，保存成自己的分析池。"
          kicker="股票池"
          tone="cool"
        >
          <div className={styles.workspaceMetrics}>
            <div className={styles.workspaceMetric}>
              <div className="helper">已选择标的</div>
              <div className={styles.workspaceMetricValue}>{selectedSymbols.length}</div>
            </div>
            <div className={styles.workspaceMetric}>
              <div className="helper">已保存股票池</div>
              <div className={styles.workspaceMetricValue}>{savedPools.length}</div>
            </div>
          </div>
          {authLoading ? <div className="helper">正在加载登录状态...</div> : null}
          {!authLoading && !isAuthenticated ? (
            <div className="surface-empty">
              <strong>登录后可保存股票池</strong>
              <div className="helper">未登录时仍可使用市场筛选和分页浏览。</div>
            </div>
          ) : (
            <div className={styles.workspaceForm}>
              <input
                className="input"
                type="text"
                value={poolName}
                onChange={(event) => setPoolName(event.target.value)}
                placeholder="输入股票池名称"
              />
              <div className="toolbar">
                <button type="button" className="primary-button" onClick={handleCreatePool}>
                  保存选中为股票池
                </button>
                <button type="button" className="stock-page-button" onClick={() => setSelectedSymbols([])} disabled={selectedSymbols.length === 0}>
                  清空已选
                </button>
              </div>
            </div>
          )}
          {workspaceMessage ? (
            <div className="helper" style={{ color: "var(--finance-rise)" }}>
              {workspaceMessage}
            </div>
          ) : null}
          <div className={styles.workspaceList}>
            {savedPools.length === 0 ? (
              <div className="helper">当前市场还没有保存的股票池。</div>
            ) : (
              savedPools.map((item) => (
                <div key={item.id} className={styles.workspaceItem}>
                  <div className={styles.workspaceItemText}>
                    <strong>{item.name}</strong>
                    <div className="helper">{`${item.symbols.length} 个标的 · ${item.market} 市场`}</div>
                  </div>
                  <div className={styles.workspaceItemActions}>
                    <button type="button" className="primary-button" onClick={() => handleAddPoolToWatch(item.symbols)}>
                      添加到观察
                    </button>
                    <button type="button" className="stock-page-button" onClick={() => setActivePoolId(item.id)}>
                      打开
                    </button>
                    <button type="button" className="stock-page-button" onClick={() => handleDeletePool(item.id)}>
                      删除
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </WorkspaceCard>

        <WorkspaceCard
          title="保存筛选器"
          helper="把关键词和行业筛选条件保存为可复用的 preset。"
          kicker="筛选器"
          tone="warm"
        >
          <div className={styles.workspaceMetrics}>
            <div className={styles.workspaceMetric}>
              <div className="helper">当前关键词</div>
              <div className={styles.workspaceMetricValue}>{keywordLabel || "--"}</div>
            </div>
            <div className={styles.workspaceMetric}>
              <div className="helper">当前类别</div>
              <div className={styles.workspaceMetricValue}>{sectorLabel || "--"}</div>
            </div>
          </div>
          {!authLoading && !isAuthenticated ? (
            <div className="surface-empty">
              <strong>登录后可保存筛选器</strong>
              <div className="helper">登录后可以在不同市场之间复用自己的筛选预设。</div>
            </div>
          ) : (
            <div className={styles.workspaceForm}>
              <input
                className="input"
                type="text"
                value={filterName}
                onChange={(event) => setFilterName(event.target.value)}
                placeholder="输入筛选器名称"
              />
              <div className="toolbar">
                <button type="button" className="primary-button" onClick={handleCreateFilter}>
                  保存当前筛选
                </button>
                <button
                  type="button"
                  className="stock-page-button"
                  onClick={() => {
                    setKeyword("");
                    setSector("");
                  }}
                >
                  清空筛选
                </button>
              </div>
            </div>
          )}
          <div className={styles.workspaceList}>
            {savedFilters.length === 0 ? (
              <div className="helper">当前市场还没有保存的筛选器。</div>
            ) : (
              savedFilters.map((item) => (
                <div key={item.id} className={styles.workspaceItem}>
                  <div className={styles.workspaceItemText}>
                    <strong>{item.name}</strong>
                    <div className="helper">{`关键词：${item.keyword || "无"} · 类别：${item.sector || "无"}`}</div>
                  </div>
                  <div className={styles.workspaceItemActions}>
                    <button type="button" className="stock-page-button" onClick={() => handleApplyFilter(item)}>
                      应用
                    </button>
                    <button type="button" className="stock-page-button" onClick={() => handleDeleteFilter(item.id)}>
                      删除
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </WorkspaceCard>
      </section>

      {activePool ? (
        <ActivePoolSection
          pool={activePool}
          compareItems={activePoolQuery.data?.items || []}
          loading={activePoolQuery.isLoading && !(activePoolQuery.data?.items || []).length}
          error={activePoolError}
          onClose={() => setActivePoolId(null)}
          onAddToWatch={() => handleAddPoolToWatch(activePool.symbols)}
          addedCount={addedToWatchCount}
        />
      ) : null}

      <MarketSection
        market={market}
        keyword={debouncedKeyword}
        sector={debouncedSector}
        selectedSymbols={selectedSymbols}
        onToggleSymbol={handleToggleSymbol}
        onSelectPage={handleSelectPage}
        onClearPage={handleClearPage}
        onTotalChange={setTotal}
      />
    </div>
  );
}
