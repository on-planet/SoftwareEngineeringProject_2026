import React, { useEffect, useMemo, useState } from "react";

import { getNewsAggregate } from "../services/api";

const PLACEHOLDER_IMAGE = "https://images.unsplash.com/photo-1504711434969-e33886168f5c?auto=format&fit=crop&w=800&q=60";

type NewsItem = {
  id: number;
  symbol: string;
  title: string;
  sentiment: string;
  published_at: string;
  link?: string;
  source?: string;
};

type NewsPage = {
  items: NewsItem[];
  total: number;
  limit: number;
  offset: number;
};

export function NewsAggregateList() {
  const [page, setPage] = useState(1);
  const [limit, setLimit] = useState(12);
  const [items, setItems] = useState<NewsItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const offset = useMemo(() => (page - 1) * limit, [page, limit]);
  const maxPage = useMemo(() => Math.max(1, Math.ceil(total / limit)), [limit, total]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getNewsAggregate({ limit, offset, sort: "desc" })
      .then((res) => {
        if (!active) return;
        const pageData = res as NewsPage;
        setItems(pageData.items ?? []);
        setTotal(pageData.total ?? 0);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) return;
        setError(err.message || "加载新闻失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [limit, offset]);

  const dedupedItems = useMemo(() => {
    const seen = new Set<string>();
    return items.filter((item) => {
      const key = [item.symbol, item.title, item.link || "", item.source || "", item.published_at].join("|");
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

  if (dedupedItems.length === 0) {
    return <div className="helper">暂无新闻</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <div className="helper">
          第 {page} / {maxPage} 页 · 共 {total} 条
        </div>
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
      {dedupedItems.map((item) => (
        <div key={item.id} className="card" style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 12 }}>
          <img src={PLACEHOLDER_IMAGE} alt="news" style={{ width: "120px", height: "80px", borderRadius: 12, objectFit: "cover" }} />
          <div>
            <div className="card-title">{item.title}</div>
            <div className="helper" style={{ marginTop: 6 }}>
              {item.symbol} · {new Date(item.published_at).toLocaleString("zh-CN")}
            </div>
            <div className="helper" style={{ marginTop: 6 }}>
              来源：{item.source || "未知"}
              {item.link ? (
                <a href={item.link} target="_blank" rel="noreferrer" style={{ marginLeft: 8, color: "var(--accent)" }}>
                  查看来源
                </a>
              ) : null}
            </div>
            <div style={{ marginTop: 6, fontSize: 12 }}>
              情绪：
              <span style={{ color: item.sentiment === "positive" ? "#ef4444" : "#10b981", fontWeight: 600 }}>
                {item.sentiment}
              </span>
            </div>
          </div>
        </div>
      ))}
      <div className="helper" style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
        <button type="button" className="input" onClick={() => setPage((value) => Math.max(1, value - 1))} disabled={page <= 1}>
          上一页
        </button>
        <span>查看更多新闻</span>
        <button type="button" className="input" onClick={() => setPage((value) => Math.min(maxPage, value + 1))} disabled={page >= maxPage}>
          下一页
        </button>
      </div>
    </div>
  );
}
