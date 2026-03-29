import React, { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";

import { AnimatedNumber } from "../motion/AnimatedNumber";
import { useApiQuery } from "../../hooks/useApiQuery";
import { NewsGraphChain, NewsGraphEntity, NewsGraphResponse } from "../../services/api";
import {
  NewsGraphMode,
  buildNewsGraphChainPath,
  buildNewsGraphChainSummary,
  buildNewsGraphFocusQueryKey,
  buildNewsGraphNodeDetails,
  buildNewsGraphOption,
  buildNewsGraphScopeImpact,
  buildNewsGraphStockQueryKey,
  dedupeNewsGraphRelatedNews,
  dedupeNewsGraphSymbols,
  formatNewsGraphCenterSummary,
  formatRelatedNewsItemMeta,
  getNewsGraphQueryOptions,
  loadNewsFocusGraph,
  loadStockNewsGraph,
  normalizeNewsGraphSymbol,
  truncateNewsGraphLabel,
} from "../../domain/newsGraph";

import styles from "./WorkspacePanels.module.css";

type PersonalWorkspaceNewsGraphPanelProps = {
  scopeLabel: string;
  symbols: string[];
  activeSymbol?: string;
  onFocusSymbolChange?: (symbol: string) => void;
};

const chipStyle: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  padding: "6px 10px",
  borderRadius: 999,
  border: "1px solid rgba(15, 23, 42, 0.08)",
  background: "rgba(255, 255, 255, 0.82)",
  fontSize: 12,
  fontWeight: 600,
};

function renderEntityGroup(title: string, items: NewsGraphEntity[], emptyText: string) {
  return (
    <div>
      <div className="card-title" style={{ fontSize: 14 }}>
        {title}
      </div>
      {items.length === 0 ? (
        <div className="helper" style={{ marginTop: 8 }}>
          {emptyText}
        </div>
      ) : (
        <div style={{ marginTop: 10, display: "flex", flexWrap: "wrap", gap: 8 }}>
          {items.map((item) => (
            <span key={item.id} style={chipStyle}>
              {item.label}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

function renderChainList(title: string, chains: NewsGraphChain[], emptyText: string) {
  return (
    <div className="card market-panel">
      <div className="card-title">{title}</div>
      <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 10 }}>
        {chains.length === 0 ? (
          <div className="helper">{emptyText}</div>
        ) : (
          chains.map((chain) => {
            const path = buildNewsGraphChainPath(chain);
            const summary = buildNewsGraphChainSummary(chain);
            return (
              <div
                key={chain.id}
                style={{
                  border: "1px solid rgba(15, 23, 42, 0.08)",
                  borderRadius: 12,
                  padding: 12,
                  background: "rgba(255, 255, 255, 0.7)",
                }}
              >
                <div className="card-title" style={{ fontSize: 14 }}>
                  {chain.title}
                </div>
                <div className="helper" style={{ marginTop: 6 }}>
                  {path}
                </div>
                {summary ? (
                  <div className="helper" style={{ marginTop: 6 }}>
                    {summary}
                  </div>
                ) : null}
                <div className="helper" style={{ marginTop: 6 }}>
                  {`strength ${chain.strength.toFixed(2)}`}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export function PersonalWorkspaceNewsGraphPanel({
  scopeLabel,
  symbols,
  activeSymbol,
  onFocusSymbolChange,
}: PersonalWorkspaceNewsGraphPanelProps) {
  const normalizedSymbols = useMemo(() => dedupeNewsGraphSymbols(symbols), [symbols]);
  const activeScopeSymbol = useMemo(() => {
    const normalized = normalizeNewsGraphSymbol(activeSymbol || "");
    return normalizedSymbols.includes(normalized) ? normalized : "";
  }, [activeSymbol, normalizedSymbols]);

  const [symbol, setSymbol] = useState("");
  const [days, setDays] = useState(7);
  const [limit, setLimit] = useState(18);
  const [mode, setMode] = useState<NewsGraphMode>("stock");
  const [focusNewsId, setFocusNewsId] = useState<number | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  useEffect(() => {
    const fallback = activeScopeSymbol || normalizedSymbols[0] || "";
    setSymbol((current) => {
      const normalized = normalizeNewsGraphSymbol(current);
      if (normalized && normalizedSymbols.includes(normalized)) {
        return activeScopeSymbol || normalized;
      }
      return fallback;
    });
  }, [activeScopeSymbol, normalizedSymbols]);

  const stockGraphQuery = useApiQuery<NewsGraphResponse>(
    mode === "stock" && symbol
      ? buildNewsGraphStockQueryKey("workspace-news-graph", symbol, days, limit)
      : null,
    () => loadStockNewsGraph(symbol, days, limit),
    getNewsGraphQueryOptions("workspace-news-graph-stock"),
  );
  const focusGraphQuery = useApiQuery<NewsGraphResponse>(
    mode === "news" && focusNewsId
      ? buildNewsGraphFocusQueryKey("workspace-news-graph", focusNewsId, days, 8)
      : null,
    () => loadNewsFocusGraph(focusNewsId as number, days, 8),
    getNewsGraphQueryOptions("workspace-news-graph-focus"),
  );

  const graphData = mode === "news" ? focusGraphQuery.data : stockGraphQuery.data;
  const loading = mode === "news" ? focusGraphQuery.isLoading : stockGraphQuery.isLoading;
  const error = mode === "news" ? focusGraphQuery.error : stockGraphQuery.error;

  useEffect(() => {
    if (!graphData?.nodes?.length) {
      setSelectedNodeId(null);
      return;
    }
    setSelectedNodeId(graphData.nodes[0]?.id ?? null);
  }, [graphData]);

  const selectedNode = useMemo(
    () => graphData?.nodes?.find((item) => item.id === selectedNodeId) ?? null,
    [graphData, selectedNodeId],
  );
  const chartOption = useMemo(
    () => (graphData ? buildNewsGraphOption(graphData) : null),
    [graphData],
  );
  const detailRows = useMemo(() => buildNewsGraphNodeDetails(selectedNode), [selectedNode]);
  const scopeImpact = useMemo(
    () => (graphData ? buildNewsGraphScopeImpact(graphData, normalizedSymbols) : null),
    [graphData, normalizedSymbols],
  );
  const drillNews = useMemo(
    () => dedupeNewsGraphRelatedNews(graphData?.related_news || [], mode === "news" ? focusNewsId : null).slice(0, 8),
    [focusNewsId, graphData, mode],
  );

  if (normalizedSymbols.length === 0) {
    return (
      <div className="surface-empty">
        <strong>{`${scopeLabel} has no symbols to explore yet.`}</strong>
        <div className="helper">Add watchlist or bought targets first, then open the workspace graph around one of those symbols.</div>
      </div>
    );
  }

  return (
    <div className={styles.stack}>
      <div className={styles.summary}>
        <div className={styles.summaryText}>
          <div className="card-title">{`${scopeLabel} News Graph Plus`}</div>
          <div className="helper">
            This workspace view shares the same propagation and impact chain contract as the full graph page, then adds
            a portfolio overlap readout for the current scope.
          </div>
        </div>
        <div className={styles.metrics}>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>Focus</div>
            <div className={styles.metricValue}>{symbol || "--"}</div>
            <div className={styles.metricHelper}>{scopeLabel}</div>
          </div>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>Related News</div>
            <div className={styles.metricValue}>
              <AnimatedNumber value={graphData?.related_news.length ?? 0} />
            </div>
            <div className={styles.metricHelper}>{`${days} day window`}</div>
          </div>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>Impact Overlap</div>
            <div className={styles.metricValue}>
              <AnimatedNumber value={scopeImpact?.overlapCount ?? 0} />
            </div>
            <div className={styles.metricHelper}>{scopeImpact?.headline ?? "waiting for graph"}</div>
          </div>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>Impact Chains</div>
            <div className={styles.metricValue}>
              <AnimatedNumber value={graphData?.impact_chains.length ?? 0} />
            </div>
            <div className={styles.metricHelper}>{`${graphData?.impact_summary.affected_symbols.length ?? 0} symbols in range`}</div>
          </div>
        </div>
      </div>

      <section className="card market-panel">
        <div className="control-bar">
          <label className="field-stack">
            <span>Symbol</span>
            <select
              className="select"
              value={symbol}
              onChange={(event) => {
                const nextSymbol = normalizeNewsGraphSymbol(event.target.value);
                setSymbol(nextSymbol);
                setMode("stock");
                setFocusNewsId(null);
                onFocusSymbolChange?.(nextSymbol);
              }}
            >
              {normalizedSymbols.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>
          <label className="field-stack">
            <span>Window</span>
            <select className="select" value={days} onChange={(event) => setDays(Number(event.target.value) || 7)}>
              <option value={3}>3 days</option>
              <option value={7}>7 days</option>
              <option value={14}>14 days</option>
            </select>
          </label>
          <label className="field-stack">
            <span>News Count</span>
            <select className="select" value={limit} onChange={(event) => setLimit(Number(event.target.value) || 18)}>
              <option value={12}>12 news</option>
              <option value={18}>18 news</option>
              <option value={24}>24 news</option>
            </select>
          </label>
          {mode === "news" ? (
            <button
              type="button"
              className="primary-button"
              onClick={() => {
                setMode("stock");
                setFocusNewsId(null);
              }}
            >
              Back to stock graph
            </button>
          ) : null}
        </div>
      </section>

      {loading ? <div className="card helper">Loading graph...</div> : null}
      {error ? <div className="card helper">{`Failed to load graph: ${error.message}`}</div> : null}

      {!loading && !error && graphData ? (
        <>
          <section className={styles.graphGrid}>
            <div className="card market-panel">
              <div className="card-title">Graph View</div>
              <div className="helper" style={{ marginTop: 6 }}>
                {formatNewsGraphCenterSummary(graphData)}
              </div>
              {chartOption ? (
                <ReactECharts
                  option={chartOption}
                  style={{ height: 440, marginTop: 12 }}
                  onEvents={{
                    click: (params: { dataType?: string; data?: { id?: string } }) => {
                      if (params.dataType === "node" && params.data?.id) {
                        setSelectedNodeId(params.data.id);
                      }
                    },
                  }}
                />
              ) : null}
            </div>

            <div className={styles.sideStack}>
              <div className="card market-panel">
                <div className="card-title">Explanation</div>
                <div style={{ marginTop: 10, fontWeight: 600 }}>{graphData.explanation.headline}</div>
                <div className="helper" style={{ marginTop: 8 }}>
                  {`Generated by ${graphData.explanation.generated_by}`}
                </div>
                <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 8 }}>
                  {graphData.explanation.evidence.map((item) => (
                    <div key={item} className="helper">
                      {item}
                    </div>
                  ))}
                </div>
                {graphData.explanation.risk_hint ? (
                  <div className="helper" style={{ marginTop: 12 }}>
                    {graphData.explanation.risk_hint}
                  </div>
                ) : null}
              </div>

              <div className="card market-panel">
                <div className="card-title">Portfolio Impact</div>
                <div className="helper" style={{ marginTop: 10 }}>
                  {scopeImpact?.headline}
                </div>
                <div className="helper" style={{ marginTop: 8 }}>
                  {scopeImpact?.detail}
                </div>
                <div className="helper" style={{ marginTop: 10 }}>
                  {`${graphData.impact_summary.related_news_count} related news | ${graphData.impact_summary.related_event_count} events | ${graphData.impact_summary.impact_chain_count} impact chains`}
                </div>
              </div>

              <div className="card market-panel">
                <div className="card-title">Node Details</div>
                {!selectedNode ? (
                  <div className="helper" style={{ marginTop: 10 }}>
                    Click a node in the graph to inspect its metadata.
                  </div>
                ) : (
                  <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
                    <div style={{ fontWeight: 700 }}>{selectedNode.label}</div>
                    {detailRows.map((row) =>
                      row.isLink ? (
                        <a key={`${row.label}-${row.value}`} href={row.value} target="_blank" rel="noreferrer" className="badge-link">
                          {row.label}
                        </a>
                      ) : (
                        <div key={`${row.label}-${row.value}`} className="helper">
                          {`${row.label}: ${row.value}`}
                        </div>
                      ),
                    )}
                  </div>
                )}
              </div>
            </div>
          </section>

          <section className={styles.graphGrid}>
            {renderChainList(
              "Propagation Chains",
              graphData.propagation_chains,
              "No propagation chain was generated for the selected window.",
            )}
            {renderChainList(
              "Impact Chains",
              graphData.impact_chains,
              "No downstream impact chain was generated for the selected window.",
            )}
          </section>

          <section className={styles.graphGrid}>
            <div className="card market-panel">
              <div className="card-title">Impact Map</div>
              <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 14 }}>
                {renderEntityGroup(
                  "Affected Sectors",
                  graphData.impact_summary.affected_sectors,
                  "No sectors are attached to the current impact summary.",
                )}
                {renderEntityGroup(
                  "Affected Stocks",
                  graphData.impact_summary.affected_symbols,
                  "No stocks are attached to the current impact summary.",
                )}
              </div>
            </div>

            <div className="card market-panel">
              <div className="card-title">Drill Into News</div>
              <div className="helper" style={{ marginTop: 6 }}>
                Pivot the graph to a specific article and keep the same chain schema inside the workspace view.
              </div>
              <div className={styles.newsList} style={{ marginTop: 10 }}>
                {drillNews.length === 0 ? <div className="helper">No additional related article is available.</div> : null}
                {drillNews.map((item) => {
                  const meta = formatRelatedNewsItemMeta(item);
                  return (
                    <button
                      key={item.id}
                      type="button"
                      className="card"
                      style={{ textAlign: "left", cursor: "pointer" }}
                      onClick={() => {
                        setFocusNewsId(item.id);
                        setMode("news");
                      }}
                    >
                      <div className="card-title" style={{ fontSize: 14 }}>
                        {truncateNewsGraphLabel(item.title, 34)}
                      </div>
                      <div className="helper" style={{ marginTop: 6 }}>
                        {meta.primary}
                      </div>
                      <div className="helper" style={{ marginTop: 6 }}>
                        {meta.secondary}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
