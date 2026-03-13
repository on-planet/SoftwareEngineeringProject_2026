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
    return <div>新闻加载中...</div>;
  }

  if (error) {
    return <div>新闻加载失败：{error}</div>;
  }

  if (items.length === 0) {
    return <div>暂无新闻</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ fontSize: 12, color: "#718096" }}>最新 {items.length} 条</div>
        <select value={limit} onChange={(event) => setLimit(Number(event.target.value) || 10)} style={{ padding: "4px 8px" }}>
          <option value={5}>5 条</option>
          <option value={10}>10 条</option>
          <option value={20}>20 条</option>
        </select>
      </div>
      {items.map((item) => (
        <div
          key={item.id}
          style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 12, background: "#fff" }}
        >
          <div style={{ fontWeight: 600 }}>{item.title}</div>
          <div style={{ marginTop: 6, fontSize: 12, color: "#718096" }}>
            {item.symbol} · {new Date(item.published_at).toLocaleString("zh-CN")}
          </div>
          <div style={{ marginTop: 6, fontSize: 12 }}>
            情绪：<span style={{ color: item.sentiment === "positive" ? "#d64545" : "#2c7a7b" }}>{item.sentiment}</span>
          </div>
        </div>
      ))}
    </div>
  );
}
