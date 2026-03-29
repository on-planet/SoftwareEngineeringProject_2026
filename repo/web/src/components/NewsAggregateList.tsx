import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiPage, getNewsAggregate, NewsItemResponse } from "../services/api";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";
import { VirtualList } from "./virtual/VirtualList";

const PLACEHOLDER_IMAGE =
  "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=800&q=60";

const SOURCE_CATEGORY_LABELS: Record<string, string> = {
  "": "All Sources",
  financial_media: "Financial Media",
  investment_research: "Research",
  international_media: "International",
  policy_media: "Policy",
  investment_community: "Community",
  finance_portal: "Portal",
  general_news: "General News",
};

const TOPIC_CATEGORY_LABELS: Record<string, string> = {
  "": "All Topics",
  macro_economy: "Macro",
  global_markets: "Global Markets",
  world_news: "World News",
  financial_policy: "Policy",
  stock_news: "Stock News",
  market_flash: "Market Flash",
  market_news: "Market News",
  funds: "Funds",
  personal_finance: "Personal Finance",
  opinion: "Opinion",
  research: "Research",
  general: "General",
};

const TIME_BUCKET_LABELS: Record<string, string> = {
  "": "All Sessions",
  pre_market: "Pre-market",
  trading_hours: "Trading",
  post_market: "Post-market",
  night: "Night",
  weekend: "Weekend",
};

type NewsPage = ApiPage<NewsItemResponse>;

type CacheMeta = {
  cache_hit?: boolean | null;
  as_of?: string | null;
  refresh_queued?: boolean | null;
};

const NEWS_AGGREGATE_CACHE_TTL_MS = 5 * 60 * 1000;
const NEWS_CARD_HEIGHT = 236;

function buildNewsAggregateCacheKey(params: {
  page: number;
  limit: number;
  sourceCategory: string;
  topicCategory: string;
  timeBucket: string;
}) {
  return [
    "news-aggregate",
    `page=${params.page}`,
    `limit=${params.limit}`,
    `source=${params.sourceCategory || "none"}`,
    `topic=${params.topicCategory || "none"}`,
    `time=${params.timeBucket || "none"}`,
  ].join(":");
}

function formatSentiment(value: string) {
  if (value === "positive") {
    return "Positive";
  }
  if (value === "negative") {
    return "Negative";
  }
  return "Neutral";
}

function sentimentColor(value: string) {
  if (value === "positive") {
    return "#b42318";
  }
  if (value === "negative") {
    return "#027a48";
  }
  return "#b54708";
}

function formatRelationValues(values?: string[] | string | null) {
  if (Array.isArray(values)) {
    return values.join(", ");
  }
  return String(values || "").trim();
}

function formatCacheSummary(meta: CacheMeta | null) {
  if (!meta) {
    return "Freshness unknown";
  }
  const parts = [meta.cache_hit ? "cache hit" : "network"];
  if (meta.as_of) {
    parts.push(`as of ${new Date(meta.as_of).toLocaleString("zh-CN")}`);
  }
  if (meta.refresh_queued) {
    parts.push("refresh queued");
  }
  return parts.join(" | ");
}

function dedupeItems(items: NewsItemResponse[]) {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = [item.symbol, item.title, item.link || "", item.source || "", item.source_site || "", item.published_at].join(
      "|",
    );
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

export function NewsAggregateList() {
  const [limit, setLimit] = useState(24);
  const [sourceCategory, setSourceCategory] = useState("");
  const [topicCategory, setTopicCategory] = useState("");
  const [timeBucket, setTimeBucket] = useState("");
  const [pages, setPages] = useState<Record<number, NewsPage>>({});
  const [total, setTotal] = useState(0);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cacheMeta, setCacheMeta] = useState<CacheMeta | null>(null);
  const inflightPages = useRef<Set<number>>(new Set());

  const resetKey = `${limit}:${sourceCategory}:${topicCategory}:${timeBucket}`;
  const loadedPages = useMemo(
    () => Object.keys(pages).map((value) => Number(value)).sort((left, right) => left - right),
    [pages],
  );
  const mergedItems = useMemo(
    () => dedupeItems(loadedPages.flatMap((pageNumber) => pages[pageNumber]?.items ?? [])),
    [loadedPages, pages],
  );
  const lastLoadedPage = loadedPages[loadedPages.length - 1] ?? 0;
  const hasMore = loadedPages.length === 0 || lastLoadedPage * limit < total;

  const loadPage = useCallback(
    async (page: number) => {
      if (inflightPages.current.has(page)) {
        return;
      }
      inflightPages.current.add(page);
      const offset = (page - 1) * limit;
      const cacheKey = buildNewsAggregateCacheKey({
        page,
        limit,
        sourceCategory,
        topicCategory,
        timeBucket,
      });
      const cachedPage = readPersistentCache<NewsPage>(cacheKey, NEWS_AGGREGATE_CACHE_TTL_MS);
      if (cachedPage) {
        setPages((prev) => ({ ...prev, [page]: cachedPage }));
        setTotal(cachedPage.total ?? 0);
        setLoadingInitial(false);
      } else if (page === 1) {
        setLoadingInitial(true);
      } else {
        setLoadingMore(true);
      }

      try {
        const response = await getNewsAggregate({
          limit,
          offset,
          sort: "desc",
          source_categories: sourceCategory ? [sourceCategory] : undefined,
          topic_categories: topicCategory ? [topicCategory] : undefined,
          time_buckets: timeBucket ? [timeBucket] : undefined,
        });
        setPages((prev) => ({ ...prev, [page]: response }));
        setTotal(response.total ?? 0);
        setCacheMeta({
          cache_hit: response.cache_hit,
          as_of: response.as_of,
          refresh_queued: response.refresh_queued,
        });
        writePersistentCache(cacheKey, response);
        setError(null);
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "Failed to load news feed");
      } finally {
        inflightPages.current.delete(page);
        setLoadingInitial(false);
        setLoadingMore(false);
      }
    },
    [limit, sourceCategory, timeBucket, topicCategory],
  );

  useEffect(() => {
    setPages({});
    setTotal(0);
    setError(null);
    setCacheMeta(null);
    inflightPages.current.clear();
    void loadPage(1);
  }, [loadPage]);

  const handleEndReached = useCallback(() => {
    if (loadingInitial || loadingMore || error || !hasMore) {
      return;
    }
    void loadPage(lastLoadedPage + 1 || 1);
  }, [error, hasMore, lastLoadedPage, loadPage, loadingInitial, loadingMore]);

  if (loadingInitial && mergedItems.length === 0) {
    return <div className="helper">Loading news feed...</div>;
  }

  if (error && mergedItems.length === 0) {
    return <div className="helper">{`News feed failed: ${error}`}</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="toolbar" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div className="helper">
          {mergedItems.length} loaded / {total} total
          <span style={{ marginLeft: 8 }}>{formatCacheSummary(cacheMeta)}</span>
        </div>
        <div className="toolbar" style={{ gap: 8, flexWrap: "wrap" }}>
          <select className="select" value={sourceCategory} onChange={(event) => setSourceCategory(event.target.value)}>
            {Object.entries(SOURCE_CATEGORY_LABELS).map(([value, label]) => (
              <option key={value || "all"} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select className="select" value={topicCategory} onChange={(event) => setTopicCategory(event.target.value)}>
            {Object.entries(TOPIC_CATEGORY_LABELS).map(([value, label]) => (
              <option key={value || "all"} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select className="select" value={timeBucket} onChange={(event) => setTimeBucket(event.target.value)}>
            {Object.entries(TIME_BUCKET_LABELS).map(([value, label]) => (
              <option key={value || "all"} value={value}>
                {label}
              </option>
            ))}
          </select>
          <select className="select" value={limit} onChange={(event) => setLimit(Number(event.target.value) || 24)}>
            <option value={12}>12 / page</option>
            <option value={24}>24 / page</option>
            <option value={48}>48 / page</option>
          </select>
        </div>
      </div>

      <VirtualList
        items={mergedItems}
        itemKey={(item) => item.id}
        itemHeight={NEWS_CARD_HEIGHT}
        height={720}
        gap={12}
        resetKey={resetKey}
        onEndReached={handleEndReached}
        emptyMessage="No news items"
        footer={
          <div className="helper" style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <span>{hasMore ? "Scroll to load more pages." : "All items loaded."}</span>
            <span>{loadingMore ? "Loading more..." : error ? `Latest error: ${error}` : "Virtualized feed active"}</span>
          </div>
        }
        renderItem={(item) => {
          const relatedSymbols = formatRelationValues(item.related_symbols);
          const relatedSectors = formatRelationValues(item.related_sectors);
          const themes = formatRelationValues(item.themes);
          const eventTags = formatRelationValues(item.event_tags);
          const keywords = formatRelationValues(item.keywords);
          const sourceLabel = item.source_site || item.source || "Unknown";
          const summaryParts = [themes, eventTags, keywords].filter(Boolean).join(" | ");

          return (
            <article
              className="card"
              style={{
                display: "grid",
                gridTemplateColumns: "128px minmax(0, 1fr)",
                gap: 12,
                height: "100%",
                overflow: "hidden",
              }}
            >
              <img
                src={PLACEHOLDER_IMAGE}
                alt="news"
                style={{ width: 128, height: 96, borderRadius: 12, objectFit: "cover" }}
              />
              <div style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 6 }}>
                <div className="card-title" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {item.title}
                </div>
                <div className="helper" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {item.symbol} | {new Date(item.published_at).toLocaleString("zh-CN")}
                </div>
                <div className="helper" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {sourceLabel}
                  {item.link ? (
                    <a href={item.link} target="_blank" rel="noreferrer" style={{ marginLeft: 8, color: "var(--accent)" }}>
                      Open
                    </a>
                  ) : null}
                </div>
                <div className="helper" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {SOURCE_CATEGORY_LABELS[item.source_category || ""] || item.source_category || "Other"} |{" "}
                  {TOPIC_CATEGORY_LABELS[item.topic_category || ""] || item.topic_category || "Other"} |{" "}
                  {TIME_BUCKET_LABELS[item.time_bucket || ""] || item.time_bucket || "Other"}
                </div>
                {relatedSymbols || relatedSectors ? (
                  <div className="helper" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {relatedSymbols ? `Symbols: ${relatedSymbols}` : ""}
                    {relatedSymbols && relatedSectors ? " | " : ""}
                    {relatedSectors ? `Sectors: ${relatedSectors}` : ""}
                  </div>
                ) : null}
                {summaryParts ? (
                  <div className="helper" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {summaryParts}
                  </div>
                ) : null}
                <div style={{ marginTop: "auto", display: "flex", gap: 12, flexWrap: "wrap", fontSize: 12 }}>
                  <span style={{ color: sentimentColor(item.sentiment), fontWeight: 700 }}>
                    {formatSentiment(item.sentiment)}
                  </span>
                  {item.impact_direction ? <span>{item.impact_direction}</span> : null}
                  {item.nlp_confidence !== null && item.nlp_confidence !== undefined ? (
                    <span>{`NLP ${item.nlp_confidence.toFixed(2)}`}</span>
                  ) : null}
                </div>
              </div>
            </article>
          );
        }}
      />
    </div>
  );
}
