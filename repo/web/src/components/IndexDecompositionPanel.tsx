import Link from "next/link";
import React, { useEffect, useMemo, useState } from "react";

import { INDEX_CONSTITUENT_OPTIONS, INDEX_NAME_MAP } from "../constants/indices";
import { getIndexInsights, type IndexInsightConstituentItem, type IndexInsightResponse } from "../services/api";
import { formatNumber, formatPercent, formatNullableNumber } from "../utils/format";

const DEFAULT_SYMBOL =
  INDEX_CONSTITUENT_OPTIONS.find((item) => item.symbol === "000300.SH")?.symbol ??
  INDEX_CONSTITUENT_OPTIONS[0]?.symbol ??
  "000300.SH";

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

function renderConstituentCell(item: IndexInsightConstituentItem) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <Link href={`/stock/${encodeURIComponent(item.symbol)}`} className="subtle-link" style={{ fontSize: 13 }}>
        {item.name || item.symbol}
      </Link>
      <span className="helper">
        {item.symbol}
        {item.sector ? ` | ${item.sector}` : ""}
      </span>
    </div>
  );
}

export function IndexDecompositionPanel() {
  const [symbol, setSymbol] = useState(DEFAULT_SYMBOL);
  const [response, setResponse] = useState<IndexInsightResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getIndexInsights(symbol)
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
        setError(err.message || "指数拆解加载失败");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [symbol]);

  const summary = response?.summary ?? null;
  const displayName = summary?.name || INDEX_NAME_MAP[symbol] || symbol;
  const sectorLeaders = useMemo(() => (response?.sector_breakdown ?? []).slice(0, 8), [response]);

  return (
    <div className="card market-panel" data-tone="cool" style={{ display: "flex", flexDirection: "column", gap: 18 }}>
      <div className="panel-header">
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          <span className="kicker">Index Decomposition</span>
          <div className="card-title" style={{ marginBottom: 0 }}>
            {displayName}
          </div>
          <div className="helper">
            聚合权重前十、行业集中度和涨跌贡献排名。A 股贡献度在缺少官方指标时按“权重 × 涨跌幅”估算。
          </div>
        </div>
        <Link href={`/indices/${encodeURIComponent(symbol)}`} className="badge-link">
          查看完整成分股
        </Link>
      </div>

      <div className="chip-group">
        {INDEX_CONSTITUENT_OPTIONS.map((item) => (
          <button
            key={item.symbol}
            type="button"
            className="chip-button"
            data-active={item.symbol === symbol}
            onClick={() => setSymbol(item.symbol)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {loading ? <div className="helper">指数拆解加载中...</div> : null}
      {!loading && error ? <div className="helper">{`指数拆解加载失败：${error}`}</div> : null}
      {!loading && !error && !response ? <div className="helper">暂无指数拆解数据。</div> : null}

      {!loading && !error && response && summary ? (
        <>
          <div className="summary-grid">
            <div className="summary-card">
              <div className="helper">成分股覆盖</div>
              <div className="metric-value">{summary.constituent_total}</div>
              <div className="metric-helper">
                已获取行情 {summary.priced_total} 只
                {summary.as_of ? ` | ${String(summary.as_of).slice(0, 10)}` : ""}
              </div>
            </div>
            <div className="summary-card">
              <div className="helper">权重集中度</div>
              <div className="metric-value">{formatWeight(summary.top10_weight)}</div>
              <div className="metric-helper">{`前五大权重 ${formatWeight(summary.top5_weight)}`}</div>
            </div>
            <div className="summary-card">
              <div className="helper">权重覆盖率</div>
              <div className="metric-value">{formatWeight(summary.weight_coverage)}</div>
              <div className="metric-helper">用于评估样本完整度</div>
            </div>
            <div className="summary-card">
              <div className="helper">涨跌分布</div>
              <div className="metric-value">{`${summary.rising_count} / ${summary.falling_count}`}</div>
              <div className="metric-helper">{`上涨 ${summary.rising_count} | 下跌 ${summary.falling_count} | 平盘 ${summary.flat_count}`}</div>
            </div>
          </div>

          <div className="split-grid">
            <div className="card">
              <div className="section-headline">
                <div>
                  <div className="card-title">权重前十</div>
                  <div className="helper">优先看指数核心暴露集中在哪些个股。</div>
                </div>
              </div>
              <div style={{ overflowX: "auto" }}>
                <table className="data-table dense-table">
                  <thead>
                    <tr>
                      <th>排名</th>
                      <th>成分股</th>
                      <th>权重</th>
                      <th>最新价</th>
                    </tr>
                  </thead>
                  <tbody>
                    {response.top_weights.map((item) => (
                      <tr key={`weight-${item.symbol}`}>
                        <td>{item.rank ?? "--"}</td>
                        <td>{renderConstituentCell(item)}</td>
                        <td>{formatWeight(item.weight)}</td>
                        <td>{formatNullableNumber(item.current)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="card">
              <div className="section-headline">
                <div>
                  <div className="card-title">涨跌贡献前十</div>
                  <div className="helper">优先展示对指数短线驱动最强的成分股。</div>
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
                    {response.top_contributors.map((item) => (
                      <tr key={`contribution-${item.symbol}`}>
                        <td>{renderConstituentCell(item)}</td>
                        <td className={trendClass(item.percent)}>{formatSignedValue(item.percent, 2, "%")}</td>
                        <td className={trendClass(item.contribution_score)}>{formatSignedValue(item.contribution_score, 2)}</td>
                        <td>{formatWeight(item.weight)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <div className="card">
            <div className="section-headline">
              <div>
                <div className="card-title">行业集中度</div>
                <div className="helper">看指数真正押注在哪些行业，以及每个行业的代表个股。</div>
              </div>
            </div>
            <div className="grid grid-3">
              {sectorLeaders.map((item) => (
                <div key={item.sector} className="metric-card">
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 10, alignItems: "center" }}>
                    <strong>{item.sector}</strong>
                    <span className="helper">{formatWeight(item.weight)}</span>
                  </div>
                  <div
                    style={{
                      marginTop: 10,
                      height: 8,
                      borderRadius: 999,
                      background: "rgba(21, 94, 239, 0.08)",
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        width: `${Math.max(4, Math.min(100, (item.weight || 0) * 100))}%`,
                        height: "100%",
                        borderRadius: 999,
                        background: "linear-gradient(135deg, #155eef 0%, #1849a9 100%)",
                      }}
                    />
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
        </>
      ) : null}
    </div>
  );
}
