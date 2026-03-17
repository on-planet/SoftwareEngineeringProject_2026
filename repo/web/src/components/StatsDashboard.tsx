import React, { useEffect, useMemo, useState } from "react";

import ReactECharts from "echarts-for-react";

import { getEventStats, getNewsStats } from "../services/api";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";

type EventStat = {
  date: string;
  count: number;
};

type EventTypeStat = {
  type: string;
  count: number;
};

type EventSymbolStat = {
  symbol: string;
  count: number;
};

type EventStatsResponse = {
  by_date: EventStat[];
  by_type: EventTypeStat[];
  by_symbol: EventSymbolStat[];
};

type NewsStat = {
  date: string;
  count: number;
};

type NewsSentimentStat = {
  sentiment: string;
  count: number;
};

type NewsSymbolStat = {
  symbol: string;
  count: number;
};

type NewsStatsResponse = {
  by_date: NewsStat[];
  by_sentiment: NewsSentimentStat[];
  by_symbol: NewsSymbolStat[];
};

type Granularity = "day" | "week" | "month";

type StatsDashboardCachePayload = {
  events: EventStatsResponse;
  news: NewsStatsResponse;
};

const STATS_DASHBOARD_CACHE_TTL_MS = 5 * 60 * 1000;

function buildStatsDashboardCacheKey(params: {
  symbol?: string;
  start?: string;
  end?: string;
  granularity: Granularity;
  topDate: number;
  topType: number;
  topSymbol: number;
  topSentiment: number;
}) {
  return [
    "stats-dashboard",
    `symbol=${params.symbol || "all"}`,
    `start=${params.start || "none"}`,
    `end=${params.end || "none"}`,
    `granularity=${params.granularity}`,
    `topDate=${params.topDate}`,
    `topType=${params.topType}`,
    `topSymbol=${params.topSymbol}`,
    `topSentiment=${params.topSentiment}`,
  ].join(":");
}

type StatCardProps<T> = {
  title: string;
  items: T[];
  getLabel: (item: T) => string;
  getCount: (item: T) => number;
};

function StatCard<T>({ title, items, getLabel, getCount }: StatCardProps<T>) {
  return (
    <div className="card">
      <div className="card-title">{title}</div>
      {items.length === 0 ? (
        <div className="helper">暂无数据</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {items.map((item, index) => (
            <div key={`${title}-${index}`} style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
              <span>{getLabel(item)}</span>
              <span style={{ fontWeight: 600 }}>{getCount(item)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function formatDate(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleDateString("zh-CN");
}

export function StatsDashboard({
  symbol,
  start,
  end,
}: {
  symbol?: string;
  start?: string;
  end?: string;
}) {
  const [granularity, setGranularity] = useState<Granularity>("day");
  const [topDate, setTopDate] = useState(30);
  const [topType, setTopType] = useState(10);
  const [topSymbol, setTopSymbol] = useState(10);
  const [topSentiment, setTopSentiment] = useState(10);
  const [events, setEvents] = useState<EventStatsResponse>({
    by_date: [],
    by_type: [],
    by_symbol: [],
  });
  const [news, setNews] = useState<NewsStatsResponse>({
    by_date: [],
    by_sentiment: [],
    by_symbol: [],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const eventDateOption = useMemo(() => {
    const labels = events.by_date.map((item) => formatDate(item.date));
    const values = events.by_date.map((item) => item.count);
    return {
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: labels },
      yAxis: { type: "value" },
      series: [{ type: "line", data: values, smooth: true }],
      grid: { left: 40, right: 20, top: 30, bottom: 40 },
    };
  }, [events.by_date]);

  const eventTypeOption = useMemo(() => {
    const labels = events.by_type.map((item) => item.type);
    const values = events.by_type.map((item) => item.count);
    return {
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: labels },
      yAxis: { type: "value" },
      series: [{ type: "bar", data: values, barMaxWidth: 36 }],
      grid: { left: 40, right: 20, top: 30, bottom: 40 },
    };
  }, [events.by_type]);

  const eventSymbolOption = useMemo(() => {
    const labels = events.by_symbol.map((item) => item.symbol);
    const values = events.by_symbol.map((item) => item.count);
    return {
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: labels },
      yAxis: { type: "value" },
      series: [{ type: "bar", data: values, barMaxWidth: 36 }],
      grid: { left: 40, right: 20, top: 30, bottom: 40 },
    };
  }, [events.by_symbol]);

  const newsDateOption = useMemo(() => {
    const labels = news.by_date.map((item) => formatDate(item.date));
    const values = news.by_date.map((item) => item.count);
    return {
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: labels },
      yAxis: { type: "value" },
      series: [{ type: "line", data: values, smooth: true }],
      grid: { left: 40, right: 20, top: 30, bottom: 40 },
    };
  }, [news.by_date]);

  const newsSentimentOption = useMemo(() => {
    const labels = news.by_sentiment.map((item) => item.sentiment);
    const values = news.by_sentiment.map((item) => item.count);
    return {
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: labels },
      yAxis: { type: "value" },
      series: [{ type: "bar", data: values, barMaxWidth: 36 }],
      grid: { left: 40, right: 20, top: 30, bottom: 40 },
    };
  }, [news.by_sentiment]);

  const newsSymbolOption = useMemo(() => {
    const labels = news.by_symbol.map((item) => item.symbol);
    const values = news.by_symbol.map((item) => item.count);
    return {
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: labels },
      yAxis: { type: "value" },
      series: [{ type: "bar", data: values, barMaxWidth: 36 }],
      grid: { left: 40, right: 20, top: 30, bottom: 40 },
    };
  }, [news.by_symbol]);

  useEffect(() => {
    let active = true;
    const cacheKey = buildStatsDashboardCacheKey({
      symbol,
      start,
      end,
      granularity,
      topDate,
      topType,
      topSymbol,
      topSentiment,
    });
    const cachedPayload = readPersistentCache<StatsDashboardCachePayload>(
      cacheKey,
      STATS_DASHBOARD_CACHE_TTL_MS,
    );
    if (cachedPayload) {
      setEvents(cachedPayload.events);
      setNews(cachedPayload.news);
      setLoading(false);
    } else {
      setLoading(true);
    }
    Promise.all([
      getEventStats({
        symbol: symbol || undefined,
        start: start || undefined,
        end: end || undefined,
        granularity,
        top_date: topDate || undefined,
        top_type: topType || undefined,
        top_symbol: topSymbol || undefined,
      }),
      getNewsStats({
        symbol: symbol || undefined,
        start: start || undefined,
        end: end || undefined,
        granularity,
        top_date: topDate || undefined,
        top_sentiment: topSentiment || undefined,
        top_symbol: topSymbol || undefined,
      }),
    ])
      .then(([eventRes, newsRes]) => {
        if (!active) {
          return;
        }
        const eventPayload = eventRes as EventStatsResponse;
        const newsPayload = newsRes as NewsStatsResponse;
        setEvents(eventPayload);
        setNews(newsPayload);
        writePersistentCache(cacheKey, {
          events: eventPayload,
          news: newsPayload,
        });
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setError(err.message || "加载统计失败");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [symbol, start, end, granularity, topDate, topType, topSymbol, topSentiment]);

  if (loading) {
    return <div className="helper">统计加载中...</div>;
  }

  if (error) {
    return <div className="helper">统计加载失败：{error}</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <section className="card">
        <div className="card-title" style={{ marginBottom: 12 }}>
          筛选条件
        </div>
        <div className="toolbar">
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            时间粒度
            <select className="select" value={granularity} onChange={(event) => setGranularity(event.target.value as Granularity)}>
              <option value="day">日</option>
              <option value="week">周</option>
              <option value="month">月</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            时间 TopN
            <input className="input" type="number" min={0} value={topDate} onChange={(event) => setTopDate(Number(event.target.value) || 0)} />
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            事件类型 TopN
            <input className="input" type="number" min={0} value={topType} onChange={(event) => setTopType(Number(event.target.value) || 0)} />
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            标的 TopN
            <input className="input" type="number" min={0} value={topSymbol} onChange={(event) => setTopSymbol(Number(event.target.value) || 0)} />
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            情绪 TopN
            <input className="input" type="number" min={0} value={topSentiment} onChange={(event) => setTopSentiment(Number(event.target.value) || 0)} />
          </label>
        </div>
      </section>

      <section>
        <h2 className="section-title">事件统计</h2>
        <div className="grid grid-3">
          <div className="card">
            <div className="card-title">按时间</div>
            <ReactECharts option={eventDateOption} style={{ height: 220 }} />
          </div>
          <div className="card">
            <div className="card-title">按类型</div>
            <ReactECharts option={eventTypeOption} style={{ height: 220 }} />
          </div>
          <div className="card">
            <div className="card-title">按标的</div>
            <ReactECharts option={eventSymbolOption} style={{ height: 220 }} />
          </div>
        </div>
        <div style={{ marginTop: 16 }}>
          <StatCard<EventStat>
            title="事件 Top 列表"
            items={events.by_date}
            getLabel={(item) => formatDate(item.date)}
            getCount={(item) => item.count}
          />
        </div>
      </section>

      <section>
        <h2 className="section-title">新闻统计</h2>
        <div className="grid grid-3">
          <div className="card">
            <div className="card-title">按时间</div>
            <ReactECharts option={newsDateOption} style={{ height: 220 }} />
          </div>
          <div className="card">
            <div className="card-title">按情绪</div>
            <ReactECharts option={newsSentimentOption} style={{ height: 220 }} />
          </div>
          <div className="card">
            <div className="card-title">按标的</div>
            <ReactECharts option={newsSymbolOption} style={{ height: 220 }} />
          </div>
        </div>
        <div style={{ marginTop: 16 }}>
          <StatCard<NewsStat>
            title="新闻 Top 列表"
            items={news.by_date}
            getLabel={(item) => formatDate(item.date)}
            getCount={(item) => item.count}
          />
        </div>
      </section>
    </div>
  );
}
