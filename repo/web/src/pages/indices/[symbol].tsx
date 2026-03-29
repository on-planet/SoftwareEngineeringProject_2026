import dynamic from "next/dynamic";
import Link from "next/link";
import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";

import { INDEX_CONSTITUENT_OPTIONS, INDEX_NAME_MAP, inferIndexMarket } from "../../constants/indices";
import { getIndexInsights, type IndexInsightConstituentItem, type IndexInsightResponse } from "../../services/api";
import { formatNumber, formatPercent, formatNullableNumber } from "../../utils/format";

const IndexKlinePanel = dynamic(
  () => import("../../components/IndexKlinePanel").then((mod) => mod.IndexKlinePanel),
  { ssr: false, loading: () => <div className="card helper">指数 K 线加载中...</div> }
);

const DEFAULT_SYMBOL =
  INDEX_CONSTITUENT_OPTIONS.find((item) => item.symbol === "000300.SH")?.symbol ??
  INDEX_CONSTITUENT_OPTIONS[0]?.symbol ??
  "000300.SH";

type SortKey =
  | "rank"
  | "weight_desc"
  | "weight_asc"
  | "percent_desc"
  | "percent_asc"
  | "contribution_desc"
  | "contribution_asc"
  | "name_asc"
  | "sector_asc";

const SORT_OPTIONS: Array<{ value: SortKey; label: string }> = [
  { value: "rank", label: "按原始排名" },
  { value: "weight_desc", label: "按权重从高到低" },
  { value: "weight_asc", label: "按权重从低到高" },
  { value: "contribution_desc", label: "按贡献度从高到低" },
  { value: "contribution_asc", label: "按贡献度从低到高" },
  { value: "percent_desc", label: "按涨跌幅从高到低" },
  { value: "percent_asc", label: "按涨跌幅从低到高" },
  { value: "name_asc", label: "按名称 A-Z" },
  { value: "sector_asc", label: "按行业 A-Z" },
];

function normalizeSymbol(value: string) {
  return (value || "").trim().toUpperCase();
}

function parseSymbolFromAsPath(asPath: string) {
  const rawPath = String(asPath || "").split("?")[0].split("#")[0];
  const segments = rawPath.split("/").filter(Boolean);
  const raw = segments[segments.length - 1] || "";
  if (!raw || raw.toLowerCase() === "indices" || raw.includes("[")) {
    return "";
  }
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}

function formatWeight(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return formatPercent(value, 2);
}

function formatSignedValue(value?: number | null, digits = 2, suffix = "") {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${Number(value).toFixed(digits)}${suffix}`;
}

function trendClass(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value) || value === 0) {
    return "trend-neutral";
  }
  return value > 0 ? "trend-up" : "trend-down";
}

function compareNullableNumber(left?: number | null, right?: number | null, direction: 1 | -1 = 1) {
  const leftValue = left ?? (direction > 0 ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY);
  const rightValue = right ?? (direction > 0 ? Number.POSITIVE_INFINITY : Number.NEGATIVE_INFINITY);
  return (leftValue - rightValue) * direction;
}

function sortConstituents(items: IndexInsightConstituentItem[], sortKey: SortKey) {
  const next = [...items];
  next.sort((left, right) => {
    switch (sortKey) {
      case "weight_desc":
        return compareNullableNumber(right.weight, left.weight);
      case "weight_asc":
        return compareNullableNumber(left.weight, right.weight);
      case "percent_desc":
        return compareNullableNumber(right.percent, left.percent);
      case "percent_asc":
        return compareNullableNumber(left.percent, right.percent);
      case "contribution_desc":
        return compareNullableNumber(right.contribution_score, left.contribution_score);
      case "contribution_asc":
        return compareNullableNumber(left.contribution_score, right.contribution_score);
      case "name_asc":
        return String(left.name || left.symbol).localeCompare(String(right.name || right.symbol), "zh-CN");
      case "sector_asc":
        return String(left.sector || "").localeCompare(String(right.sector || ""), "zh-CN");
      case "rank":
      default:
        return compareNullableNumber(left.rank, right.rank);
    }
  });
  return next;
}

function renderConstituentLink(item: IndexInsightConstituentItem) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <Link href={`/stock/${encodeURIComponent(item.symbol)}`} className="subtle-link" style={{ fontSize: 13 }}>
        {item.name || item.symbol}
      </Link>
      <span className="helper">{item.symbol}</span>
    </div>
  );
}

export default function IndexDetailPage() {
  const router = useRouter();
  const routeSymbol = useMemo(() => {
    if (typeof router.query.symbol === "string" && router.query.symbol.trim()) {
      return router.query.symbol;
    }
    return parseSymbolFromAsPath(router.asPath || "") || DEFAULT_SYMBOL;
  }, [router.asPath, router.query.symbol]);
  const activeSymbol = useMemo(() => normalizeSymbol(routeSymbol) || DEFAULT_SYMBOL, [routeSymbol]);
  const [response, setResponse] = useState<IndexInsightResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("weight_desc");
  const [pageSize, setPageSize] = useState(20);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setPage(1);
  }, [activeSymbol, search, sortKey, pageSize]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getIndexInsights(activeSymbol)
      .then((payload) => {
        if (!active) {
          return;
        }
        setResponse(payload);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setResponse(null);
        setError(err.message || "指数详情加载失败");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [activeSymbol]);

  const summary = response?.summary ?? null;
  const filteredItems = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    const base = response?.constituents ?? [];
    const filtered = keyword
      ? base.filter((item) =>
          [item.symbol, item.name, item.sector].some((field) => String(field || "").toLowerCase().includes(keyword))
        )
      : base;
    return sortConstituents(filtered, sortKey);
  }, [response, search, sortKey]);

  const maxPage = useMemo(() => Math.max(1, Math.ceil(filteredItems.length / pageSize)), [filteredItems.length, pageSize]);
  const pagedItems = useMemo(() => {
    const offset = (page - 1) * pageSize;
    return filteredItems.slice(offset, offset + pageSize);
  }, [filteredItems, page, pageSize]);

  useEffect(() => {
    if (page > maxPage) {
      setPage(maxPage);
    }
  }, [maxPage, page]);

  const activeMarket = summary?.market === "HK" ? "HK" : inferIndexMarket(activeSymbol);
  const displayName = summary?.name || INDEX_NAME_MAP[activeSymbol] || activeSymbol;
  const sectorPreview = response?.sector_breakdown.slice(0, 6) ?? [];

  const pushSymbol = (symbol: string) => {
    void router.push(`/indices/${encodeURIComponent(symbol)}`);
  };

  return (
    <div className="page">
      <section className="card hero-card">
        <div className="page-header">
          <div>
            <h1 className="page-title">指数详情</h1>
            <p className="helper">这里是成分股主入口，支持搜索、排序、分页，以及指数拆解摘要和行情联动。</p>
          </div>
          <div className="toolbar">
            <select className="select" value={activeSymbol} onChange={(event) => pushSymbol(event.target.value)}>
              {INDEX_CONSTITUENT_OPTIONS.map((item) => (
                <option key={item.symbol} value={item.symbol}>
                  {item.label}
                </option>
              ))}
            </select>
            <Link href="/insights" className="badge-link">
              返回洞察
            </Link>
          </div>
        </div>

        <div className="summary-grid" style={{ marginTop: 18 }}>
          <div className="summary-card">
            <div className="helper">当前指数</div>
            <div className="metric-value">{displayName}</div>
            <div className="metric-helper">
              {activeSymbol}
              {summary?.as_of ? ` | ${String(summary.as_of).slice(0, 10)}` : ""}
            </div>
          </div>
          <div className="summary-card">
            <div className="helper">成分股数量</div>
            <div className="metric-value">{summary?.constituent_total ?? "--"}</div>
            <div className="metric-helper">{`已取到行情 ${summary?.priced_total ?? 0} 只`}</div>
          </div>
          <div className="summary-card">
            <div className="helper">前十大权重</div>
            <div className="metric-value">{summary ? formatWeight(summary.top10_weight) : "--"}</div>
            <div className="metric-helper">{`前五大权重 ${summary ? formatWeight(summary.top5_weight) : "--"}`}</div>
          </div>
          <div className="summary-card">
            <div className="helper">涨跌分布</div>
            <div className="metric-value">
              {summary ? `${summary.rising_count} / ${summary.falling_count}` : "--"}
            </div>
            <div className="metric-helper">
              {summary ? `上涨 ${summary.rising_count} | 下跌 ${summary.falling_count} | 平盘 ${summary.flat_count}` : "等待数据"}
            </div>
          </div>
        </div>
      </section>

      <section>
        <IndexKlinePanel
          symbol={activeSymbol}
          activeMarket={activeMarket}
          onMarketChange={(market) => {
            const target = INDEX_CONSTITUENT_OPTIONS.find((item) => item.market === market)?.symbol;
            if (target) {
              pushSymbol(target);
            }
          }}
          onSymbolChange={pushSymbol}
        />
      </section>

      {!loading && !error && response ? (
        <>
          <section className="split-grid">
            <div className="card">
              <div className="section-headline">
                <div>
                  <div className="card-title">权重前十</div>
                  <div className="helper">先看指数最核心的暴露位置。</div>
                </div>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table className="data-table dense-table">
                  <thead>
                    <tr>
                      <th>排名</th>
                      <th>成分股</th>
                      <th>权重</th>
                      <th>涨跌幅</th>
                    </tr>
                  </thead>
                  <tbody>
                    {response.top_weights.slice(0, 10).map((item) => (
                      <tr key={`top-weight-${item.symbol}`}>
                        <td>{item.rank ?? "--"}</td>
                        <td>{renderConstituentLink(item)}</td>
                        <td>{formatWeight(item.weight)}</td>
                        <td className={trendClass(item.percent)}>{formatSignedValue(item.percent, 2, "%")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="card">
              <div className="section-headline">
                <div>
                  <div className="card-title">贡献排名</div>
                  <div className="helper">A 股优先展示估算贡献度，港股优先展示官方贡献点数。</div>
                </div>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table className="data-table dense-table">
                  <thead>
                    <tr>
                      <th>成分股</th>
                      <th>涨跌幅</th>
                      <th>贡献度</th>
                      <th>权重</th>
                    </tr>
                  </thead>
                  <tbody>
                    {response.top_contributors.slice(0, 10).map((item) => (
                      <tr key={`top-contribution-${item.symbol}`}>
                        <td>{renderConstituentLink(item)}</td>
                        <td className={trendClass(item.percent)}>{formatSignedValue(item.percent, 2, "%")}</td>
                        <td className={trendClass(item.contribution_score)}>{formatSignedValue(item.contribution_score, 2)}</td>
                        <td>{formatWeight(item.weight)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </section>

          <section>
            <div className="card">
              <div className="section-headline">
                <div>
                  <div className="card-title">行业集中度</div>
                  <div className="helper">帮助判断指数暴露在少数行业还是更均衡分布。</div>
                </div>
              </div>
              <div className="grid grid-3">
                {sectorPreview.map((item) => (
                  <div key={item.sector} className="metric-card">
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 10 }}>
                      <strong>{item.sector}</strong>
                      <span className="helper">{formatWeight(item.weight)}</span>
                    </div>
                    <div className="metric-helper">{`成分股 ${formatNumber(item.symbol_count)} 只`}</div>
                    <div className={`metric-helper ${trendClass(item.avg_percent)}`}>
                      {`行业平均涨跌幅 ${formatSignedValue(item.avg_percent, 2, "%")}`}
                    </div>
                    <div className="metric-helper">
                      {item.leader_name || item.leader_symbol ? `代表个股 ${item.leader_name || item.leader_symbol}` : "暂无代表个股"}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </>
      ) : null}

      <section>
        <div className="section-headline">
          <div>
            <h2 className="section-title">完整成分股列表</h2>
            <div className="helper">支持搜索、排序和分页，适合作为指数明细主入口。</div>
          </div>
        </div>
        <div className="card">
          <div className="toolbar" style={{ justifyContent: "space-between" }}>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <input
                className="input"
                type="text"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="搜索代码、名称或行业"
              />
              <select className="select" value={sortKey} onChange={(event) => setSortKey(event.target.value as SortKey)}>
                {SORT_OPTIONS.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </div>
            <select className="select" value={pageSize} onChange={(event) => setPageSize(Number(event.target.value) || 20)}>
              <option value={10}>10 条</option>
              <option value={20}>20 条</option>
              <option value={50}>50 条</option>
            </select>
          </div>

          {loading ? <div className="helper" style={{ marginTop: 12 }}>成分股明细加载中...</div> : null}
          {!loading && error ? <div className="helper" style={{ marginTop: 12 }}>{`指数详情加载失败：${error}`}</div> : null}
          {!loading && !error && filteredItems.length === 0 ? <div className="helper" style={{ marginTop: 12 }}>暂无匹配的成分股。</div> : null}

          {!loading && !error && filteredItems.length > 0 ? (
            <>
              <div className="helper" style={{ marginTop: 12 }}>
                {`共 ${filteredItems.length} 只成分股，当前第 ${page} / ${maxPage} 页`}
              </div>
              <div style={{ overflowX: "auto", marginTop: 12 }}>
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>排名</th>
                      <th>成分股</th>
                      <th>行业</th>
                      <th>权重</th>
                      <th>最新价</th>
                      <th>涨跌额</th>
                      <th>涨跌幅</th>
                      <th>贡献度</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pagedItems.map((item) => (
                      <tr key={`row-${item.symbol}`}>
                        <td>{item.rank ?? "--"}</td>
                        <td>{renderConstituentLink(item)}</td>
                        <td>{item.sector || "--"}</td>
                        <td>{formatWeight(item.weight)}</td>
                        <td>{formatNullableNumber(item.current)}</td>
                        <td className={trendClass(item.change)}>{formatSignedValue(item.change, 2)}</td>
                        <td className={trendClass(item.percent)}>{formatSignedValue(item.percent, 2, "%")}</td>
                        <td className={trendClass(item.contribution_score)}>{formatSignedValue(item.contribution_score, 2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="stock-pagination">
                <div className="helper">
                  {`展示 ${(page - 1) * pageSize + 1}-${Math.min(page * pageSize, filteredItems.length)} / ${filteredItems.length}`}
                </div>
                <div className="stock-pagination-actions">
                  <button
                    type="button"
                    className="stock-page-button"
                    onClick={() => setPage((value) => Math.max(1, value - 1))}
                    disabled={page <= 1}
                  >
                    上一页
                  </button>
                  <button
                    type="button"
                    className="stock-page-button"
                    onClick={() => setPage((value) => Math.min(maxPage, value + 1))}
                    disabled={page >= maxPage}
                  >
                    下一页
                  </button>
                </div>
              </div>
            </>
          ) : null}
        </div>
      </section>
    </div>
  );
}
