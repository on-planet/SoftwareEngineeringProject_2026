import React, { useEffect, useMemo, useState } from "react";

import { getNewsAggregate } from "../services/api";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";

const PLACEHOLDER_IMAGE =
  "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=800&q=60";

const SOURCE_CATEGORY_LABELS: Record<string, string> = {
  "": "全部站点分类",
  financial_media: "财经媒体",
  investment_research: "投行研究",
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
  stock_news: "个股资讯",
  market_flash: "财经快讯",
  market_news: "市场新闻",
  funds: "基金",
  personal_finance: "个人理财",
  opinion: "专栏观点",
  research: "研究",
  general: "综合",
};

const TIME_BUCKET_LABELS: Record<string, string> = {
  "": "全部时间分类",
  pre_market: "盘前",
  trading_hours: "交易时段",
  post_market: "盘后",
  night: "夜间",
  weekend: "周末",
};

type NewsItem = {
  id: number;
  symbol: string;
  title: string;
  sentiment: string;
  published_at: string;
  link?: string;
  source?: string;
  source_site?: string;
  source_category?: string;
  topic_category?: string;
  time_bucket?: string;
  related_symbols?: string;
  related_sectors?: string;
};

type NewsPage = {
  items: NewsItem[];
  total: number;
  limit: number;
  offset: number;
};

const NEWS_AGGREGATE_CACHE_TTL_MS = 5 * 60 * 1000;

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
    return "#ef4444";
  }
  if (value === "negative") {
    return "#10b981";
  }
  return "#f59e0b";
}

export function NewsAggregateList() {
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(12);
  const [sourceCategory, setSourceCategory] = useState("");
  const [topicCategory, setTopicCategory] = useState("");
  const [timeBucket, setTimeBucket] = useState("");
  const [items, setItems] = useState<NewsItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const offset = useMemo(() => (page - 1) * limit, [page, limit]);
  const maxPage = useMemo(() => Math.max(1, Math.ceil(total / limit)), [limit, total]);

  useEffect(() => {
    setPage(1);
  }, [sourceCategory, topicCategory, timeBucket]);

  useEffect(() => {
    let active = true;
    const cacheKey = buildNewsAggregateCacheKey({
      page,
      limit,
      sourceCategory,
      topicCategory,
      timeBucket,
    });
    const cachedPage = readPersistentCache<NewsPage>(cacheKey, NEWS_AGGREGATE_CACHE_TTL_MS);
    if (cachedPage) {
      setItems(cachedPage.items ?? []);
      setTotal(cachedPage.total ?? 0);
      setLoading(false);
    } else {
      setLoading(true);
    }
    getNewsAggregate({
      limit,
      offset,
      sort: "desc",
      source_categories: sourceCategory ? [sourceCategory] : undefined,
      topic_categories: topicCategory ? [topicCategory] : undefined,
      time_buckets: timeBucket ? [timeBucket] : undefined,
    })
      .then((res) => {
        if (!active) {
          return;
        }
        const pageData = res as NewsPage;
        setItems(pageData.items ?? []);
        setTotal(pageData.total ?? 0);
        writePersistentCache(cacheKey, pageData);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setError(err.message || "新闻加载失败");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [limit, offset, sourceCategory, timeBucket, topicCategory]);

  const dedupedItems = useMemo(() => {
    const seen = new Set<string>();
    return items.filter((item) => {
      const key = [
        item.symbol,
        item.title,
        item.link || "",
        item.source || "",
        item.source_site || "",
        item.published_at,
      ].join("|");
      if (seen.has(key)) {
        return false;
      }
      seen.add(key);
      return true;
    });
  }, [items]);

  if (loading) {
    return <div className="helper">新闻加载中...</div>;
  }

  if (error) {
    return <div className="helper">新闻加载失败：{error}</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="toolbar" style={{ justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
        <div className="helper">
          第 {page} / {maxPage} 页 · 共 {total} 条
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
          <select
            className="select"
            value={limit}
            onChange={(event) => {
              setLimit(Number(event.target.value) || 12);
              setPage(1);
            }}
          >
            <option value={8}>8 条</option>
            <option value={12}>12 条</option>
            <option value={20}>20 条</option>
          </select>
        </div>
      </div>

      {dedupedItems.length === 0 ? <div className="helper">暂无新闻</div> : null}

      {dedupedItems.map((item) => (
        <div
          key={item.id}
          className="card"
          style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 12 }}
        >
          <img
            src={PLACEHOLDER_IMAGE}
            alt="news"
            style={{ width: "120px", height: "80px", borderRadius: 12, objectFit: "cover" }}
          />
          <div>
            <div className="card-title">{item.title}</div>
            <div className="helper" style={{ marginTop: 6 }}>
              {item.symbol} · {new Date(item.published_at).toLocaleString("zh-CN")}
            </div>
            <div className="helper" style={{ marginTop: 6 }}>
              来源站点：{item.source_site || item.source || "未知"}
              {item.link ? (
                <a
                  href={item.link}
                  target="_blank"
                  rel="noreferrer"
                  style={{ marginLeft: 8, color: "var(--accent)" }}
                >
                  查看来源
                </a>
              ) : null}
            </div>
            <div className="helper" style={{ marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap" }}>
              <span>站点分类：{SOURCE_CATEGORY_LABELS[item.source_category || ""] || item.source_category || "未知"}</span>
              <span>主题：{TOPIC_CATEGORY_LABELS[item.topic_category || ""] || item.topic_category || "未知"}</span>
              <span>时间分类：{TIME_BUCKET_LABELS[item.time_bucket || ""] || item.time_bucket || "未知"}</span>
            </div>
            {item.related_symbols || item.related_sectors ? (
              <div className="helper" style={{ marginTop: 6, display: "flex", gap: 8, flexWrap: "wrap" }}>
                {item.related_symbols ? <span>关联个股：{item.related_symbols}</span> : null}
                {item.related_sectors ? <span>关联板块：{item.related_sectors}</span> : null}
              </div>
            ) : null}
            <div style={{ marginTop: 6, fontSize: 12 }}>
              情绪：
              <span style={{ color: sentimentColor(item.sentiment), fontWeight: 600, marginLeft: 4 }}>
                {formatSentiment(item.sentiment)}
              </span>
            </div>
          </div>
        </div>
      ))}

      <div
        className="helper"
        style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}
      >
        <button
          type="button"
          className="input"
          onClick={() => setPage((value) => Math.max(1, value - 1))}
          disabled={page <= 1}
        >
          上一页
        </button>
        <span>按站点分类、主题分类、时间分类浏览新闻</span>
        <button
          type="button"
          className="input"
          onClick={() => setPage((value) => Math.min(maxPage, value + 1))}
          disabled={page >= maxPage}
        >
          下一页
        </button>
      </div>
    </div>
  );
}
