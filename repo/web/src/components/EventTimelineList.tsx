import React, { useEffect, useState } from "react";

import { getEventTimeline } from "../services/api";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";
import styles from "./EventTimelineList.module.css";

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

function formatEventType(value?: string) {
  return String(value || "event").replace(/_/g, " ");
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
    <div className={styles.timelineList}>
      <div className={`helper ${styles.timelineTotal}`}>{`${TEXT.totalPrefix} ${total} ${TEXT.totalSuffix}`}</div>
      {items.map((item, index) => (
        <article
          key={`${item.symbol}-${item.date}-${index}`}
          className={`card ${styles.timelineCard}`}
        >
          <div className={styles.timelineRail}>
            <div className={styles.timelineSymbol}>{item.symbol || "--"}</div>
            <div className={styles.timelineType}>{formatEventType(item.type)}</div>
            <div className={styles.timelineDate}>{item.date || "--"}</div>
          </div>
          <div className={styles.timelineContent}>
            <div className="card-title">{item.title}</div>
            <div className={styles.timelineMeta}>
              <span className={styles.timelineMetaItem}>
                <span className={styles.timelineLabel}>{TEXT.source}</span>
                {item.source || TEXT.unknown}
              </span>
            </div>
            {item.link ? (
              <div className={`helper ${styles.timelineFooter}`}>
                <a href={item.link} target="_blank" rel="noreferrer" className={styles.sourceLink}>
                  {TEXT.openSource}
                </a>
              </div>
            ) : null}
          </div>
        </article>
      ))}
    </div>
  );
}
