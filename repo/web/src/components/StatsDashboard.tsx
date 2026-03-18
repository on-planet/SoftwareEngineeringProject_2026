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
type StatsDashboardView = "all" | "events" | "news";

type StatsDashboardCachePayload = {
  events: EventStatsResponse;
  news: NewsStatsResponse;
};

const STATS_DASHBOARD_CACHE_TTL_MS = 5 * 60 * 1000;

function buildStatsDashboardCacheKey(params: {
  symbol?: string;
  symbolsKey?: string;
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
    `symbols=${params.symbolsKey || "none"}`,
    `start=${params.start || "none"}`,
    `end=${params.end || "none"}`,
    `granularity=${params.granularity}`,
    `topDate=${params.topDate}`,
    `topType=${params.topType}`,
    `topSymbol=${params.topSymbol}`,
    `topSentiment=${params.topSentiment}`,
  ].join(":");
}

function normalizeSymbols(values: string[] | undefined) {
  if (!values || values.length === 0) {
    return [];
  }
  const unique = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const symbol = (value || "").trim().toUpperCase();
    if (!symbol || unique.has(symbol)) {
      continue;
    }
    unique.add(symbol);
    result.push(symbol);
  }
  return result;
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
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {items.map((item, index) => (
            <div key={`${title}-${index}`} className="stats-row">
              <span>{getLabel(item)}</span>
              <span className="stats-row-value">{getCount(item)}</span>
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

function buildLineOption(params: {
  labels: string[];
  values: number[];
  color: string;
  areaColor: string;
  title: string;
}) {
  return {
    color: [params.color],
    tooltip: { trigger: "axis" },
    grid: { left: 42, right: 24, top: 28, bottom: 38 },
    xAxis: { type: "category", data: params.labels, axisTick: { show: false } },
    yAxis: { type: "value", splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.2)" } } },
    series: [
      {
        name: params.title,
        type: "line",
        data: params.values,
        smooth: true,
        symbol: "circle",
        symbolSize: 7,
        lineStyle: { width: 3 },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: params.areaColor },
              { offset: 1, color: "rgba(255,255,255,0.02)" },
            ],
          },
        },
      },
    ],
  };
}

function buildBarOption(params: {
  labels: string[];
  values: number[];
  color: string;
  title: string;
}) {
  return {
    color: [params.color],
    tooltip: { trigger: "axis" },
    grid: { left: 42, right: 24, top: 28, bottom: 38 },
    xAxis: { type: "category", data: params.labels, axisTick: { show: false } },
    yAxis: { type: "value", splitLine: { lineStyle: { color: "rgba(148, 163, 184, 0.2)" } } },
    series: [
      {
        name: params.title,
        type: "bar",
        data: params.values,
        barMaxWidth: 34,
        itemStyle: {
          borderRadius: [8, 8, 0, 0],
        },
      },
    ],
  };
}

function sumByCount(items: Array<{ count: number }>) {
  return items.reduce((acc, item) => acc + (Number.isFinite(item.count) ? item.count : 0), 0);
}

type MetricCardProps = {
  label: string;
  value: number;
  helper: string;
};

function MetricCard({ label, value, helper }: MetricCardProps) {
  return (
    <div className="stats-overview-card">
      <div className="helper">{label}</div>
      <div className="stats-overview-value">{value}</div>
      <div className="stats-overview-helper">{helper}</div>
    </div>
  );
}

export function StatsDashboard({
  symbol,
  symbols,
  start,
  end,
  view = "all",
}: {
  symbol?: string;
  symbols?: string[];
  start?: string;
  end?: string;
  view?: StatsDashboardView;
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
  const showEventSection = view !== "news";
  const showNewsSection = view !== "events";
  const normalizedSymbols = useMemo(() => normalizeSymbols(symbols), [symbols]);
  const symbolsKey = useMemo(() => normalizedSymbols.join(","), [normalizedSymbols]);

  const eventTotals = useMemo(() => {
    return {
      total: sumByCount(events.by_date),
      typeCount: events.by_type.length,
      symbolCount: events.by_symbol.length,
    };
  }, [events]);

  const newsTotals = useMemo(() => {
    return {
      total: sumByCount(news.by_date),
      sentimentCount: news.by_sentiment.length,
      symbolCount: news.by_symbol.length,
    };
  }, [news]);

  const eventDateOption = useMemo(() => {
    return buildLineOption({
      labels: events.by_date.map((item) => formatDate(item.date)),
      values: events.by_date.map((item) => item.count),
      color: "#2563eb",
      areaColor: "rgba(37, 99, 235, 0.28)",
      title: "事件数量",
    });
  }, [events.by_date]);

  const eventTypeOption = useMemo(() => {
    return buildBarOption({
      labels: events.by_type.map((item) => item.type),
      values: events.by_type.map((item) => item.count),
      color: "#0891b2",
      title: "事件类型",
    });
  }, [events.by_type]);

  const eventSymbolOption = useMemo(() => {
    return buildBarOption({
      labels: events.by_symbol.map((item) => item.symbol),
      values: events.by_symbol.map((item) => item.count),
      color: "#0f766e",
      title: "事件标的",
    });
  }, [events.by_symbol]);

  const newsDateOption = useMemo(() => {
    return buildLineOption({
      labels: news.by_date.map((item) => formatDate(item.date)),
      values: news.by_date.map((item) => item.count),
      color: "#f59e0b",
      areaColor: "rgba(245, 158, 11, 0.3)",
      title: "新闻数量",
    });
  }, [news.by_date]);

  const newsSentimentOption = useMemo(() => {
    return buildBarOption({
      labels: news.by_sentiment.map((item) => item.sentiment),
      values: news.by_sentiment.map((item) => item.count),
      color: "#d97706",
      title: "新闻情绪",
    });
  }, [news.by_sentiment]);

  const newsSymbolOption = useMemo(() => {
    return buildBarOption({
      labels: news.by_symbol.map((item) => item.symbol),
      values: news.by_symbol.map((item) => item.count),
      color: "#b45309",
      title: "新闻标的",
    });
  }, [news.by_symbol]);

  useEffect(() => {
    let active = true;
    const cacheKey = buildStatsDashboardCacheKey({
      symbol,
      symbolsKey,
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
        symbols: normalizedSymbols.length > 0 ? normalizedSymbols : undefined,
        symbol: symbol || undefined,
        start: start || undefined,
        end: end || undefined,
        granularity,
        top_date: topDate || undefined,
        top_type: topType || undefined,
        top_symbol: topSymbol || undefined,
      }),
      getNewsStats({
        symbols: normalizedSymbols.length > 0 ? normalizedSymbols : undefined,
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
  }, [symbol, symbolsKey, start, end, granularity, topDate, topType, topSymbol, topSentiment]);

  if (loading) {
    return <div className="helper">统计加载中...</div>;
  }

  if (error) {
    return <div className="helper">{`统计加载失败：${error}`}</div>;
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

      {showEventSection ? (
        <section className="stats-section-block">
        <div className="stats-section-head">
          <h2 className="section-title" style={{ marginBottom: 0 }}>
            事件统计
          </h2>
          <span className="stats-section-tag">Event Analytics</span>
        </div>
        <div className="stats-overview-grid">
          <MetricCard label="事件总量" value={eventTotals.total} helper="按时间维度累计" />
          <MetricCard label="事件类型数" value={eventTotals.typeCount} helper="当前筛选窗口内" />
          <MetricCard label="覆盖标的数" value={eventTotals.symbolCount} helper="按标的聚合后" />
        </div>
        <div className="grid grid-3">
          <div className="card">
            <div className="card-title">按时间</div>
            <ReactECharts option={eventDateOption} style={{ height: 240 }} />
          </div>
          <div className="card">
            <div className="card-title">按类型</div>
            <ReactECharts option={eventTypeOption} style={{ height: 240 }} />
          </div>
          <div className="card">
            <div className="card-title">按标的</div>
            <ReactECharts option={eventSymbolOption} style={{ height: 240 }} />
          </div>
        </div>
        <StatCard<EventStat>
          title="事件 Top 列表"
          items={events.by_date}
          getLabel={(item) => formatDate(item.date)}
          getCount={(item) => item.count}
        />
        </section>
      ) : null}

      {showNewsSection ? (
        <section className="stats-section-block stats-section-block-warm">
        <div className="stats-section-head">
          <h2 className="section-title" style={{ marginBottom: 0 }}>
            新闻统计
          </h2>
          <span className="stats-section-tag stats-section-tag-warm">News Analytics</span>
        </div>
        <div className="stats-overview-grid">
          <MetricCard label="新闻总量" value={newsTotals.total} helper="按时间维度累计" />
          <MetricCard label="情绪类别数" value={newsTotals.sentimentCount} helper="正向 / 负向 / 中性等" />
          <MetricCard label="覆盖标的数" value={newsTotals.symbolCount} helper="按标的聚合后" />
        </div>
        <div className="grid grid-3">
          <div className="card">
            <div className="card-title">按时间</div>
            <ReactECharts option={newsDateOption} style={{ height: 240 }} />
          </div>
          <div className="card">
            <div className="card-title">按情绪</div>
            <ReactECharts option={newsSentimentOption} style={{ height: 240 }} />
          </div>
          <div className="card">
            <div className="card-title">按标的</div>
            <ReactECharts option={newsSymbolOption} style={{ height: 240 }} />
          </div>
        </div>
        <StatCard<NewsStat>
          title="新闻 Top 列表"
          items={news.by_date}
          getLabel={(item) => formatDate(item.date)}
          getCount={(item) => item.count}
        />
        </section>
      ) : null}
    </div>
  );
}
