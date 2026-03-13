import React, { useEffect, useState } from "react";

import { getNews } from "../services/api";

type NewsItem = {
  id: number;
  symbol: string;
  title: string;
  sentiment: string;
  published_at: string;
};

type NewsPage = {
  items: NewsItem[];
  total: number;
  limit: number;
  offset: number;
};

type Props = {
  symbol: string;
};

export function NewsList({ symbol }: Props) {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [limit, setLimit] = useState(10);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getNews(symbol, { limit })
      .then((res) => {
        if (!active) {
          return;
        }
        const page = res as NewsPage;
        setItems(page.items ?? []);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setError(err.message || "加载新闻失败");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [symbol, limit]);

  if (loading) {
    return <div className="helper">新闻加载中...</div>;
  }

  if (error) {
    return <div className="helper">新闻加载失败：{error}</div>;
  }

  if (items.length === 0) {
    return <div className="helper">暂无新闻</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <div className="helper">最新 {items.length} 条</div>
        <select className="select" value={limit} onChange={(event) => setLimit(Number(event.target.value) || 10)}>
          <option value={5}>5 条</option>
          <option value={10}>10 条</option>
          <option value={20}>20 条</option>
        </select>
      </div>
      {items.map((item) => (
        <div key={item.id} className="card">
          <div className="card-title">{item.title}</div>
          <div className="helper" style={{ marginTop: 6 }}>
            {item.symbol} · {new Date(item.published_at).toLocaleString("zh-CN")}
          </div>
          <div style={{ marginTop: 6, fontSize: 12 }}>
            情绪：
            <span style={{ color: item.sentiment === "positive" ? "#f87171" : "#34d399", fontWeight: 600 }}>
              {item.sentiment}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
