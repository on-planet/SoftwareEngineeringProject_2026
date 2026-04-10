import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { ApiPage, getNewsAggregate, NewsItemResponse } from "../services/api";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";
import { VirtualList } from "./virtual/VirtualList";

const PLACEHOLDER_IMAGE =
  "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=800&q=60";

const SOURCE_CATEGORY_LABELS: Record<string, string> = {
  "": "全部来源",
  financial_media: "财经媒体",
  investment_research: "投研机构",
  international_media: "国际媒体",
  policy_media: "政策媒体",
  investment_community: "投资社区",
  finance_portal: "财经门户",
  general_news: "综合新闻",
};

const TOPIC_CATEGORY_LABELS: Record<string, string> = {
  "": "全部主题",
  macro_economy: "宏观经济",
  global_markets: "全球市场",
  world_news: "国际新闻",
  financial_policy: "金融政策",
  stock_news: "股票新闻",
  market_flash: "市场快讯",
  market_news: "市场新闻",
  funds: "基金",
  personal_finance: "个人理财",
  opinion: "观点",
  research: "研究报告",
  general: "综合",
};

const TIME_BUCKET_LABELS: Record<string, string> = {
  "": "全部时段",
  pre_market: "盘前",
  trading_hours: "交易时段",
  post_market: "盘后",
  night: "夜间",
  weekend: "周末",
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
    return "正面";
  }
  if (value === "negative") {
    return "负面";
  }
  return "中性";
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
    return "新鲜度未知";
  }
  const parts = [meta.cache_hit ? "缓存命中" : "网络请求"];
  if (meta.as_of) {
    parts.push(`截至 ${new Date(meta.as_of).toLocaleString("zh-CN")}`);
  }
  if (meta.refresh_queued) {
    parts.push("刷新已排队");
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
        setError(nextError instanceof Error ? nextError.message : "加载新闻失败");
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
    return <div className="helper">新闻加载中...</div>;
  }

  if (error && mergedItems.length === 0) {
    return <div className="helper">{`新闻加载失败：${error}`}</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="toolbar" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div className="helper">
          已加载 {mergedItems.length} / 共 {total} 条
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
            <option value={12}>12 条/页</option>
            <option value={24}>24 条/页</option>
            <option value={48}>48 条/页</option>
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
        emptyMessage="暂无新闻"
        footer={
          <div className="helper" style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
            <span>{hasMore ? "滚动加载更多页面。" : "已加载全部内容。"}</span>
            <span>{loadingMore ? "加载更多..." : error ? `最新错误：${error}` : "虚拟化列表已激活"}</span>
          </div>
        }
        renderItem={(item) => {
          const relatedSymbols = formatRelationValues(item.related_symbols);
          const relatedSectors = formatRelationValues(item.related_sectors);
          const themes = formatRelationValues(item.themes);
          const eventTags = formatRelationValues(item.event_tags);
          const keywords = formatRelationValues(item.keywords);
          const sourceLabel = item.source_site || item.source || "未知";
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
                      打开
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
                    {relatedSymbols ? `相关标的：${relatedSymbols}` : ""}
                    {relatedSymbols && relatedSectors ? " | " : ""}
                    {relatedSectors ? `相关板块：${relatedSectors}` : ""}
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
