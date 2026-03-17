import React, { useEffect, useState } from "react";

import { getEventTimeline } from "../services/api";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";

const PLACEHOLDER_IMAGE =
  "https://images.unsplash.com/flagged/photo-1559116315-702b0b4774ce?auto=format&fit=crop&w=800&q=60";

const TEXT = {
  loadError: "\u52a0\u8f7d\u4e8b\u4ef6\u5931\u8d25",
  loading: "\u4e8b\u4ef6\u52a0\u8f7d\u4e2d...",
  empty: "\u6682\u65e0\u4e8b\u4ef6",
  totalPrefix: "\u5171",
  totalSuffix: "\u6761",
  source: "\u6765\u6e90",
  unknown: "\u672a\u77e5",
  openSource: "\u67e5\u770b\u6765\u6e90",
};

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

const EVENT_TIMELINE_CACHE_TTL_MS = 5 * 60 * 1000;

function buildEventTimelineCacheKey() {
  return "event-timeline:list:limit=20:offset=0:sort=desc";
}

export function EventTimelineList() {
  const [items, setItems] = useState<EventItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const cacheKey = buildEventTimelineCacheKey();
    const cachedPage = readPersistentCache<EventPage>(cacheKey, EVENT_TIMELINE_CACHE_TTL_MS);
    if (cachedPage) {
      setItems(cachedPage.items ?? []);
      setTotal(cachedPage.total ?? 0);
      setLoading(false);
    } else {
      setLoading(true);
    }
    getEventTimeline({ limit: 20, offset: 0, sort: "desc" })
      .then((res) => {
        if (!active) {
          return;
        }
        const page = res as EventPage;
        setItems(page.items ?? []);
        setTotal(page.total ?? 0);
        writePersistentCache(cacheKey, page);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setError(err.message || TEXT.loadError);
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return <div className="helper">{TEXT.loading}</div>;
  }

  if (error) {
    return <div className="helper">{`${TEXT.loadError}: ${error}`}</div>;
  }

  if (items.length === 0) {
    return <div className="helper">{TEXT.empty}</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div className="helper">{`${TEXT.totalPrefix} ${total} ${TEXT.totalSuffix}`}</div>
      {items.map((item, index) => (
        <div
          key={`${item.symbol}-${item.date}-${index}`}
          className="card"
          style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 12 }}
        >
          <img
            src={PLACEHOLDER_IMAGE}
            alt="event"
            style={{ width: "120px", height: "80px", borderRadius: 12, objectFit: "cover" }}
          />
          <div>
            <div className="card-title">{item.title}</div>
            <div className="helper" style={{ marginTop: 6 }}>
              {item.symbol}
              {` | ${item.type} | ${item.date}`}
            </div>
            <div className="helper" style={{ marginTop: 6 }}>
              {`${TEXT.source}: ${item.source || TEXT.unknown}`}
              {item.link ? (
                <a href={item.link} target="_blank" rel="noreferrer" style={{ marginLeft: 8, color: "var(--accent)" }}>
                  {TEXT.openSource}
                </a>
              ) : null}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
