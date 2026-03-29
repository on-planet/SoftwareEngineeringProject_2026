import {
  ApiQueryOptions,
  NewsGraphChain,
  NewsGraphEntity,
  NewsGraphNode,
  NewsGraphResponse,
  NewsItemResponse,
  getNewsFocusGraph,
  getStockNewsGraph,
} from "../services/api";

export type NewsGraphMode = "stock" | "news";

const NEWS_GRAPH_STALE_TIME_MS = 2 * 60 * 1000;
const NEWS_GRAPH_CACHE_TIME_MS = 10 * 60 * 1000;

export function normalizeNewsGraphSymbol(value: string) {
  return (value || "").trim().toUpperCase();
}

export function dedupeNewsGraphSymbols(values: string[]) {
  const seen = new Set<string>();
  const output: string[] = [];
  values.forEach((value) => {
    const symbol = normalizeNewsGraphSymbol(value);
    if (!symbol || seen.has(symbol)) {
      return;
    }
    seen.add(symbol);
    output.push(symbol);
  });
  return output;
}

export function buildNewsGraphStockQueryKey(
  scopeKey: string,
  symbol: string,
  days: number,
  limit: number,
) {
  return [scopeKey, "stock", normalizeNewsGraphSymbol(symbol), days, limit];
}

export function buildNewsGraphFocusQueryKey(
  scopeKey: string,
  newsId: number,
  days: number,
  limit: number,
) {
  return [scopeKey, "news", newsId, days, limit];
}

export function getNewsGraphQueryOptions(label = "news-graph"): ApiQueryOptions {
  return {
    staleTimeMs: NEWS_GRAPH_STALE_TIME_MS,
    cacheTimeMs: NEWS_GRAPH_CACHE_TIME_MS,
    retry: 1,
    label,
  };
}

export async function loadStockNewsGraph(symbol: string, days: number, limit: number) {
  return getStockNewsGraph(symbol, { days, limit });
}

export async function loadNewsFocusGraph(newsId: number, days: number, limit: number) {
  return getNewsFocusGraph(newsId, { days, limit });
}

export function getNewsGraphNodeColor(node: NewsGraphNode) {
  if (node.type === "stock") {
    return "#1d4ed8";
  }
  if (node.type === "sector") {
    return "#d97706";
  }
  if (node.type === "event") {
    return "#dc2626";
  }
  if (node.type === "theme") {
    return "#7c3aed";
  }
  if (node.sentiment === "positive") {
    return "#ef4444";
  }
  if (node.sentiment === "negative") {
    return "#10b981";
  }
  return "#64748b";
}

export function getNewsGraphNodeSymbol(node: NewsGraphNode) {
  if (node.type === "stock") {
    return "circle";
  }
  if (node.type === "sector") {
    return "diamond";
  }
  if (node.type === "event") {
    return "triangle";
  }
  if (node.type === "theme") {
    return "roundRect";
  }
  return "circle";
}

export function truncateNewsGraphLabel(value: string, limit = 18) {
  const text = String(value || "").trim();
  if (text.length <= limit) {
    return text;
  }
  return `${text.slice(0, Math.max(1, limit - 1)).trim()}...`;
}

export function buildNewsGraphOption(graph: NewsGraphResponse) {
  return {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      formatter: (params: { dataType?: string; data?: NewsGraphNode & { label?: string } }) => {
        if (params.dataType === "node" && params.data) {
          return `${params.data.type}<br/>${params.data.label}`;
        }
        return "";
      },
    },
    animationDuration: 600,
    series: [
      {
        type: "graph",
        layout: "force",
        roam: true,
        draggable: true,
        data: graph.nodes.map((node) => ({
          ...node,
          symbol: getNewsGraphNodeSymbol(node),
          symbolSize: node.size,
          itemStyle: {
            color: getNewsGraphNodeColor(node),
            opacity: node.type === "news" ? 0.92 : 1,
          },
          label: {
            show: true,
            color: "#0f172a",
            fontSize: node.type === "news" ? 11 : 12,
            formatter: truncateNewsGraphLabel(node.label, node.type === "news" ? 16 : 18),
          },
        })),
        links: graph.edges.map((edge) => ({
          ...edge,
          lineStyle: {
            width: Math.max(1, edge.weight * 2.4),
            opacity: edge.type === "cooccurs_event" || edge.type === "related_news" ? 0.45 : 0.7,
            curveness: edge.type === "mentions_peer" ? 0.18 : 0.08,
          },
          label: edge.label
            ? {
                show: false,
                formatter: edge.label,
              }
            : undefined,
        })),
        force: {
          repulsion: 260,
          gravity: 0.08,
          edgeLength: [60, 140],
        },
        emphasis: {
          focus: "adjacency",
          lineStyle: {
            width: 3,
          },
        },
      },
    ],
  };
}

export function buildNewsGraphNodeDetails(node: NewsGraphNode | null) {
  if (!node) {
    return [];
  }
  const metadata = node.metadata || {};
  const details: Array<{ label: string; value: string; isLink?: boolean }> = [
    { label: "Type", value: node.type },
  ];
  if (node.sentiment) {
    details.push({ label: "Sentiment", value: node.sentiment });
  }
  [
    ["Title", metadata.title],
    ["Symbol", metadata.symbol],
    ["Sector", metadata.sector],
    ["Event", metadata.type],
    ["Published", metadata.published_at],
    ["Date", metadata.date],
    ["NLP Event", metadata.event_type],
    ["Direction", metadata.impact_direction],
  ].forEach(([label, value]) => {
    if (value) {
      details.push({ label: String(label), value: String(value) });
    }
  });
  if (Array.isArray(metadata.themes) && metadata.themes.length) {
    details.push({ label: "Themes", value: metadata.themes.join(", ") });
  }
  if (Array.isArray(metadata.keywords) && metadata.keywords.length) {
    details.push({ label: "Keywords", value: metadata.keywords.join(", ") });
  }
  if (metadata.link) {
    details.push({ label: "Source", value: String(metadata.link), isLink: true });
  }
  return details;
}

export function buildNewsGraphChainPath(chain: NewsGraphChain) {
  return chain.steps.map((step) => step.label).join(" -> ");
}

export function buildNewsGraphChainSummary(chain: NewsGraphChain) {
  const summary = String(chain.summary || "").trim();
  if (!summary) {
    return null;
  }
  return summary === buildNewsGraphChainPath(chain) ? null : summary;
}

export function dedupeNewsGraphRelatedNews(items: NewsItemResponse[], excludeNewsId?: number | null) {
  const seen = new Set<number>();
  return items.filter((item) => {
    if (!item || seen.has(item.id)) {
      return false;
    }
    if (excludeNewsId !== undefined && excludeNewsId !== null && item.id === excludeNewsId) {
      return false;
    }
    seen.add(item.id);
    return true;
  });
}

export function extractNewsGraphEntitySymbol(entity: NewsGraphEntity) {
  if (entity.type !== "stock") {
    return "";
  }
  if (entity.id.startsWith("stock:")) {
    return normalizeNewsGraphSymbol(entity.id.slice("stock:".length));
  }
  const matched = entity.label.match(/\(([A-Za-z0-9._-]+)\)$/);
  if (matched?.[1]) {
    return normalizeNewsGraphSymbol(matched[1]);
  }
  return normalizeNewsGraphSymbol(entity.label);
}

export function buildNewsGraphScopeImpact(graph: NewsGraphResponse, scopeSymbols: string[]) {
  const normalizedScope = dedupeNewsGraphSymbols(scopeSymbols);
  const affectedSymbols = dedupeNewsGraphSymbols(
    (graph.impact_summary?.affected_symbols || []).map((item) => extractNewsGraphEntitySymbol(item)),
  );
  const overlapSymbols = affectedSymbols.filter((symbol) => normalizedScope.includes(symbol));
  return {
    affectedSymbols,
    overlapSymbols,
    scopeCount: normalizedScope.length,
    overlapCount: overlapSymbols.length,
    headline:
      normalizedScope.length === 0
        ? "No scoped symbols were provided."
        : overlapSymbols.length > 0
          ? `${overlapSymbols.length}/${normalizedScope.length} scoped symbols sit inside the current impact zone.`
          : "No scoped symbols overlap the current impact zone.",
    detail:
      overlapSymbols.length > 0
        ? overlapSymbols.join(", ")
        : graph.impact_summary?.portfolio_hint || "Switch the focus symbol to test portfolio spillover.",
  };
}

export function formatNewsGraphCenterSummary(graph: NewsGraphResponse) {
  return `${graph.center_label} | ${graph.center_type} | ${graph.days}d`;
}

export function formatRelatedNewsItemMeta(item: NewsItemResponse) {
  const publishedAt = item.published_at
    ? new Date(item.published_at).toLocaleString("zh-CN")
    : "--";
  const themes = item.themes?.slice(0, 2).join(", ") || "--";
  return {
    primary: `${item.symbol} | ${publishedAt}`,
    secondary: `event ${item.event_type || "--"} | themes ${themes}`,
  };
}
