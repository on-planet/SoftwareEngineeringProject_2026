import React, { useEffect, useState } from "react";

import { getEventTimeline } from "../services/api";

const PLACEHOLDER_IMAGE = "https://images.unsplash.com/flagged/photo-1559116315-702b0b4774ce?auto=format&fit=crop&w=800&q=60";

type EventItem = {
  symbol: string;
  type: string;
  title: string;
  date: string;
  link?: string;
  source?: string;
};

type EventPage = {
  items: EventItem[];
  total: number;
  limit: number;
  offset: number;
};

export function EventTimelineList() {
  const [items, setItems] = useState<EventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getEventTimeline({ limit: 20, offset: 0, sort: "desc" })
      .then((res) => {
        if (!active) return;
        const page = res as EventPage;
        setItems(page.items ?? []);
        setTotal(page.total ?? 0);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) return;
        setError(err.message || "加载事件失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return <div className="helper">事件加载中...</div>;
  }

  if (error) {
    return <div className="helper">事件加载失败：{error}</div>;
  }

  if (items.length === 0) {
    return <div className="helper">暂无事件</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="helper">共 {total} 条</div>
      {items.map((item, index) => (
        <div key={`${item.symbol}-${item.date}-${index}`} className="card" style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 12 }}>
          <img src={PLACEHOLDER_IMAGE} alt="event" style={{ width: "120px", height: "80px", borderRadius: 12, objectFit: "cover" }} />
          <div>
            <div className="card-title">{item.title}</div>
            <div className="helper" style={{ marginTop: 6 }}>
              {item.symbol} · {item.type} · {item.date}
            </div>
            <div className="helper" style={{ marginTop: 6 }}>
              来源：{item.source || "未知"}
              {item.link ? (
                <a href={item.link} target="_blank" rel="noreferrer" style={{ marginLeft: 8, color: "var(--accent)" }}>
                  查看来源
                </a>
              ) : null}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
