import React, { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";

import { useApiQuery } from "../hooks/useApiQuery";
import { NewsGraphChain, NewsGraphEntity, NewsGraphResponse } from "../services/api";
import {
  NewsGraphMode,
  buildNewsGraphChainPath,
  buildNewsGraphChainSummary,
  buildNewsGraphFocusQueryKey,
  buildNewsGraphNodeDetails,
  buildNewsGraphOption,
  buildNewsGraphStockQueryKey,
  dedupeNewsGraphRelatedNews,
  formatNewsGraphCenterSummary,
  formatRelatedNewsItemMeta,
  getNewsGraphQueryOptions,
  loadNewsFocusGraph,
  loadStockNewsGraph,
  normalizeNewsGraphSymbol,
  truncateNewsGraphLabel,
} from "../domain/newsGraph";

const DEFAULT_SYMBOL = "000001.SH";

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
    <div className="stack-md">
      <div className="card-title" style={{ fontSize: 14 }}>
        {title}
      </div>
      {items.length === 0 ? (
        <div className="helper">{emptyText}</div>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
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
    <div className="card surface-panel">
      <div className="card-title">{title}</div>
      <div className="stack-md" style={{ marginTop: 12 }}>
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
                <div className="stack-sm" style={{ marginTop: 10 }}>
                  {chain.steps.map((step, index) => (
                    <div key={`${chain.id}-${step.id}-${index}`} className="helper">
                      {step.relation ? `${step.relation}: ${step.label}` : step.label}
                    </div>
                  ))}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

export function NewsRelationGraph() {
  const [mode, setMode] = useState<NewsGraphMode>("stock");
  const [symbol, setSymbol] = useState(DEFAULT_SYMBOL);
  const [draftSymbol, setDraftSymbol] = useState(DEFAULT_SYMBOL);
  const [days, setDays] = useState(7);
  const [limit, setLimit] = useState(18);
  const [focusNewsId, setFocusNewsId] = useState<number | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const stockGraphQuery = useApiQuery<NewsGraphResponse>(
    mode === "stock" && symbol
      ? buildNewsGraphStockQueryKey("news-graph", symbol, days, limit)
      : null,
    () => loadStockNewsGraph(symbol, days, limit),
    getNewsGraphQueryOptions("news-graph-stock"),
  );
  const focusGraphQuery = useApiQuery<NewsGraphResponse>(
    mode === "news" && focusNewsId
      ? buildNewsGraphFocusQueryKey("news-graph", focusNewsId, days, 8)
      : null,
    () => loadNewsFocusGraph(focusNewsId as number, days, 8),
    getNewsGraphQueryOptions("news-graph-focus"),
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
  const drillNews = useMemo(
    () => dedupeNewsGraphRelatedNews(graphData?.related_news || [], mode === "news" ? focusNewsId : null).slice(0, 8),
    [focusNewsId, graphData, mode],
  );

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalized = normalizeNewsGraphSymbol(draftSymbol);
    if (!normalized) {
      return;
    }
    setSymbol(normalized);
    setMode("stock");
    setFocusNewsId(null);
  };

  return (
    <div className="stack-lg">
      <section className="card surface-panel">
        <div className="section-headline">
          <div>
            <div className="card-title">新闻关系图谱</div>
            <div className="helper">
              本图谱同时展示传播链和影响链，可追踪新闻从报道到板块、个股及下游溢出的完整路径。
            </div>
          </div>
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
        <form className="control-bar" onSubmit={handleSubmit}>
          <input
            className="input"
            value={draftSymbol}
            onChange={(event) => setDraftSymbol(event.target.value)}
            placeholder="输入股票代码，例如 000001.SH"
          />
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
          <button type="submit" className="primary-button">
            构建图谱
          </button>
        </form>
      </section>

      {loading ? <div className="card surface-panel helper">图谱加载中...</div> : null}
      {error ? <div className="card surface-panel helper">{`图谱加载失败：${error.message}`}</div> : null}

      {!loading && !error && graphData ? (
        <>
          <div className="metric-grid">
            <div className="metric-panel">
              <div className="metric-panel__label">中心节点</div>
              <div className="metric-panel__value">{graphData.center_label}</div>
              <div className="metric-panel__helper">{formatNewsGraphCenterSummary(graphData)}</div>
            </div>
            <div className="metric-panel">
              <div className="metric-panel__label">传播链</div>
              <div className="metric-panel__value">{graphData.propagation_chains.length}</div>
              <div className="metric-panel__helper">{`${graphData.related_news.length} 条相关新闻`}</div>
            </div>
            <div className="metric-panel">
              <div className="metric-panel__label">影响链</div>
              <div className="metric-panel__value">{graphData.impact_chains.length}</div>
              <div className="metric-panel__helper">{`${graphData.impact_summary.affected_symbols.length} 个受影响标的`}</div>
            </div>
            <div className="metric-panel">
              <div className="metric-panel__label">情绪</div>
              <div className="metric-panel__value">{graphData.impact_summary.dominant_sentiment || "--"}</div>
              <div className="metric-panel__helper">{graphData.impact_summary.dominant_direction || "无方向标签"}</div>
            </div>
          </div>

          <section className="layout-two-col">
            <div className="card surface-panel">
              <div className="card-title">图谱视图</div>
              <div className="helper">{formatNewsGraphCenterSummary(graphData)}</div>
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

            <div className="stack-md">
              <div className="card surface-panel">
                <div className="card-title">图谱解释</div>
                <div className="stack-md" style={{ marginTop: 12 }}>
                  <div style={{ fontWeight: 600 }}>{graphData.explanation.headline}</div>
                  <div className="helper">{`生成者：${graphData.explanation.generated_by}`}</div>
                  {graphData.explanation.evidence.map((item) => (
                    <div key={item} className="helper">
                      {item}
                    </div>
                  ))}
                  {graphData.explanation.risk_hint ? (
                    <div className="helper">{graphData.explanation.risk_hint}</div>
                  ) : null}
                </div>
              </div>

              <div className="card surface-panel">
                <div className="card-title">影响摘要</div>
                <div className="stack-md" style={{ marginTop: 12 }}>
                  <div className="helper">
                    {`${graphData.impact_summary.related_news_count} 条相关新闻 | ${graphData.impact_summary.related_event_count} 个事件 | ${graphData.impact_summary.propagation_chain_count} 条传播链 | ${graphData.impact_summary.impact_chain_count} 条影响链`}
                  </div>
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

              <div className="card surface-panel">
                <div className="card-title">节点详情</div>
                {!selectedNode ? (
                  <div className="helper" style={{ marginTop: 12 }}>
                    点击图谱中的节点查看其元数据。
                  </div>
                ) : (
                  <div className="stack-md" style={{ marginTop: 12 }}>
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

          <section className="layout-two-col">
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

          <section className="layout-two-col">
            <div className="card surface-panel">
              <div className="card-title">相关事件</div>
              <div className="stack-md" style={{ marginTop: 12 }}>
                {graphData.related_events.length === 0 ? (
                  <div className="helper">所选时间窗口未找到相关事件。</div>
                ) : (
                  graphData.related_events.map((item) => (
                    <div key={item.id} className="helper">
                      {`${item.date} | ${item.type} | ${item.title}`}
                    </div>
                  ))
                )}
              </div>
            </div>
            <div className="card surface-panel">
              <div className="card-title">深入新闻</div>
              <div className="helper">打开相关文章并以该新闻为中心重建图谱。</div>
              <div className="stack-md" style={{ marginTop: 10, maxHeight: 320, overflowY: "auto" }}>
                {drillNews.length === 0 ? <div className="helper">No additional related article is available.</div> : null}
                {drillNews.map((item) => {
                  const meta = formatRelatedNewsItemMeta(item);
                  return (
                    <button
                      key={item.id}
                      type="button"
                      className="card surface-panel"
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
