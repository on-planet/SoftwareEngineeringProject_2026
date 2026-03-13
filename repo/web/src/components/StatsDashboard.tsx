import React, { useEffect, useMemo, useState } from "react";

import ReactECharts from "echarts-for-react";

import { getEventStats, getNewsStats } from "../services/api";

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

type StatCardProps<T> = {
  title: string;
  items: T[];
  getLabel: (item: T) => string;
  getCount: (item: T) => number;
};

function StatCard<T>({ title, items, getLabel, getCount }: StatCardProps<T>) {
  return (
    <div
      style={{
        border: "1px solid #e2e8f0",
        borderRadius: 10,
        padding: 16,
        background: "#fff",
        boxShadow: "0 1px 2px rgba(0,0,0,0.06)",
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 10 }}>{title}</div>
      {items.length === 0 ? (
        <div style={{ fontSize: 12, color: "#718096" }}>暂无数据</div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {items.map((item, index) => (
            <div
              key={`${title}-${index}`}
              style={{
                display: "flex",
                justifyContent: "space-between",
                fontSize: 13,
              }}
            >
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
    setLoading(true);
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
        setEvents(eventRes as EventStatsResponse);
        setNews(newsRes as NewsStatsResponse);
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
    return <div>统计加载中...</div>;
  }

  if (error) {
    return <div>统计加载失败：{error}</div>;
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
      <section
        style={{
          border: "1px solid #edf2f7",
          borderRadius: 12,
          padding: 16,
          background: "#f8fafc",
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: 12 }}>筛选条件</div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            时间粒度
            <select
              value={granularity}
              onChange={(event) => setGranularity(event.target.value as Granularity)}
              style={{ padding: "6px 8px" }}
            >
              <option value="day">日</option>
              <option value="week">周</option>
              <option value="month">月</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            时间 TopN
            <input
              type="number"
              min={0}
              value={topDate}
              onChange={(event) => setTopDate(Number(event.target.value) || 0)}
              style={{ padding: "6px 8px" }}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            事件类型 TopN
            <input
              type="number"
              min={0}
              value={topType}
              onChange={(event) => setTopType(Number(event.target.value) || 0)}
              style={{ padding: "6px 8px" }}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            标的 TopN
            <input
              type="number"
              min={0}
              value={topSymbol}
              onChange={(event) => setTopSymbol(Number(event.target.value) || 0)}
              style={{ padding: "6px 8px" }}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            情绪 TopN
            <input
              type="number"
              min={0}
              value={topSentiment}
              onChange={(event) => setTopSentiment(Number(event.target.value) || 0)}
              style={{ padding: "6px 8px" }}
            />
          </label>
        </div>
      </section>

      <section>
        <h2 style={{ fontSize: 18, marginBottom: 12 }}>事件统计</h2>
        <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
          <div style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, background: "#fff" }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>按时间</div>
            <ReactECharts option={eventDateOption} style={{ height: 220 }} />
          </div>
          <div style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, background: "#fff" }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>按类型</div>
            <ReactECharts option={eventTypeOption} style={{ height: 220 }} />
          </div>
          <div style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, background: "#fff" }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>按标的</div>
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
        <h2 style={{ fontSize: 18, marginBottom: 12 }}>新闻统计</h2>
        <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
          <div style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, background: "#fff" }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>按时间</div>
            <ReactECharts option={newsDateOption} style={{ height: 220 }} />
          </div>
          <div style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, background: "#fff" }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>按情绪</div>
            <ReactECharts option={newsSentimentOption} style={{ height: 220 }} />
          </div>
          <div style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, background: "#fff" }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>按标的</div>
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
