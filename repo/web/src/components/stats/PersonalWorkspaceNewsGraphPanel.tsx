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
                  {`强度 ${chain.strength.toFixed(2)}`}
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
        <strong>{`${scopeLabel} 暂无标的可探索`}</strong>
        <div className="helper">请先添加自选或已买标的，然后以其中一个标的为中心打开工作区图谱。</div>
      </div>
    );
  }

  return (
    <div className={styles.stack}>
      <div className={styles.summary}>
        <div className={styles.summaryText}>
          <div className="card-title">{`${scopeLabel} 新闻关系图谱`}</div>
          <div className="helper">
            本工作区视图与完整图谱页面共用相同的传播链和影响链协议，同时为当前范围添加了组合重叠读数。
          </div>
        </div>
        <div className={styles.metrics}>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>聚焦</div>
            <div className={styles.metricValue}>{symbol || "--"}</div>
            <div className={styles.metricHelper}>{scopeLabel}</div>
          </div>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>相关新闻</div>
            <div className={styles.metricValue}>
              <AnimatedNumber value={graphData?.related_news.length ?? 0} />
            </div>
            <div className={styles.metricHelper}>{`${days} 天窗口`}</div>
          </div>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>影响重叠</div>
            <div className={styles.metricValue}>
              <AnimatedNumber value={scopeImpact?.overlapCount ?? 0} />
            </div>
            <div className={styles.metricHelper}>{scopeImpact?.headline ?? "等待图谱加载"}</div>
          </div>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>影响链</div>
            <div className={styles.metricValue}>
              <AnimatedNumber value={graphData?.impact_chains.length ?? 0} />
            </div>
            <div className={styles.metricHelper}>{`${graphData?.impact_summary.affected_symbols.length ?? 0} 个标的中`}</div>
          </div>
        </div>
      </div>

      <section className="card market-panel">
        <div className="control-bar">
          <label className="field-stack">
            <span>标的</span>
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
            <span>时间窗口</span>
            <select className="select" value={days} onChange={(event) => setDays(Number(event.target.value) || 7)}>
              <option value={3}>3 天</option>
              <option value={7}>7 天</option>
              <option value={14}>14 天</option>
            </select>
          </label>
          <label className="field-stack">
            <span>新闻数量</span>
            <select className="select" value={limit} onChange={(event) => setLimit(Number(event.target.value) || 18)}>
              <option value={12}>12 条</option>
              <option value={18}>18 条</option>
              <option value={24}>24 条</option>
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
              返回个股图谱
            </button>
          ) : null}
        </div>
      </section>

      {loading ? <div className="card helper">图谱加载中...</div> : null}
      {error ? <div className="card helper">{`图谱加载失败：${error.message}`}</div> : null}

      {!loading && !error && graphData ? (
        <>
          <section className={styles.graphGrid}>
            <div className="card market-panel">
              <div className="card-title">图谱视图</div>
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
                <div className="card-title">图谱解释</div>
                <div style={{ marginTop: 10, fontWeight: 600 }}>{graphData.explanation.headline}</div>
                <div className="helper" style={{ marginTop: 8 }}>
                  {`生成者：${graphData.explanation.generated_by}`}
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
                <div className="card-title">组合影响</div>
                <div className="helper" style={{ marginTop: 10 }}>
                  {scopeImpact?.headline}
                </div>
                <div className="helper" style={{ marginTop: 8 }}>
                  {scopeImpact?.detail}
                </div>
                <div className="helper" style={{ marginTop: 10 }}>
                  {`${graphData.impact_summary.related_news_count} 条相关新闻 | ${graphData.impact_summary.related_event_count} 个事件 | ${graphData.impact_summary.impact_chain_count} 条影响链`}
                </div>
              </div>

              <div className="card market-panel">
                <div className="card-title">节点详情</div>
                {!selectedNode ? (
                  <div className="helper" style={{ marginTop: 10 }}>
                    点击图谱中的节点查看其元数据。
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
              "传播链",
              graphData.propagation_chains,
              "所选时间窗口未生成传播链。",
            )}
            {renderChainList(
              "影响链",
              graphData.impact_chains,
              "所选时间窗口未生成下游影响链。",
            )}
          </section>

          <section className={styles.graphGrid}>
            <div className="card market-panel">
              <div className="card-title">影响地图</div>
              <div style={{ marginTop: 12, display: "flex", flexDirection: "column", gap: 14 }}>
                {renderEntityGroup(
                  "受影响板块",
                  graphData.impact_summary.affected_sectors,
                  "当前影响摘要未关联板块。",
                )}
                {renderEntityGroup(
                  "受影响个股",
                  graphData.impact_summary.affected_symbols,
                  "当前影响摘要未关联个股。",
                )}
              </div>
            </div>

            <div className="card market-panel">
              <div className="card-title">深入新闻</div>
              <div className="helper" style={{ marginTop: 6 }}>
                将图谱中心切换到特定文章，并在工作区视图中保持相同的链式结构。
              </div>
              <div className={styles.newsList} style={{ marginTop: 10 }}>
                {drillNews.length === 0 ? <div className="helper">暂无其他相关文章。</div> : null}
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
