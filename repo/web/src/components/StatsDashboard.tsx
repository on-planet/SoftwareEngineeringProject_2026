import React, { useMemo, useState } from "react";

import ReactECharts from "echarts-for-react";

import { AnimatedNumber } from "./motion/AnimatedNumber";
import { useApiQuery } from "../hooks/useApiQuery";
import { DashboardStatsOverviewResponse } from "../services/api";
import {
  StatsOverviewGranularity,
  buildStatsOverviewQueryKey,
  getStatsOverviewQueryOptions,
  loadStatsOverview,
  normalizeStatsOverviewResponse,
  normalizeStatsSymbols,
} from "../domain/statsOverview";

type StatsDashboardView = "all" | "events" | "news";

type EventDateStat = DashboardStatsOverviewResponse["events"]["by_date"][number];
type EventTypeStat = DashboardStatsOverviewResponse["events"]["by_type"][number];
type EventSymbolStat = DashboardStatsOverviewResponse["events"]["by_symbol"][number];
type NewsDateStat = DashboardStatsOverviewResponse["news"]["by_date"][number];
type NewsSentimentStat = DashboardStatsOverviewResponse["news"]["by_sentiment"][number];
type NewsSymbolStat = DashboardStatsOverviewResponse["news"]["by_symbol"][number];

type StatCardProps<T> = {
  title: string;
  items: T[];
  getLabel: (item: T) => string;
  getCount: (item: T) => number;
};

function StatCard<T>({ title, items, getLabel, getCount }: StatCardProps<T>) {
  return (
    <div className="card surface-panel">
      <div className="card-title">{title}</div>
      {items.length === 0 ? (
        <div className="helper">No data.</div>
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
    <div className="metric-panel">
      <div className="metric-panel__label">{label}</div>
      <div className="metric-panel__value">
        <AnimatedNumber value={value} />
      </div>
      <div className="metric-panel__helper">{helper}</div>
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
  const [granularity, setGranularity] = useState<StatsOverviewGranularity>("day");
  const [topDate, setTopDate] = useState(30);
  const [topType, setTopType] = useState(10);
  const [topSymbol, setTopSymbol] = useState(10);
  const [topSentiment, setTopSentiment] = useState(10);
  const showEventSection = view !== "news";
  const showNewsSection = view !== "events";
  const normalizedSymbols = useMemo(() => normalizeStatsSymbols(symbols), [symbols]);

  const queryParams = useMemo(
    () => ({
      symbol,
      symbols: normalizedSymbols,
      start,
      end,
      granularity,
      topDate,
      topType,
      topSymbol,
      topSentiment,
    }),
    [end, granularity, normalizedSymbols, start, symbol, topDate, topSentiment, topSymbol, topType],
  );
  const statsQueryKey = useMemo(() => buildStatsOverviewQueryKey(queryParams), [queryParams]);
  const statsQuery = useApiQuery<DashboardStatsOverviewResponse>(
    statsQueryKey,
    () => loadStatsOverview(queryParams),
    getStatsOverviewQueryOptions(statsQueryKey),
  );

  const statsPayload = useMemo(
    () => normalizeStatsOverviewResponse(statsQuery.data, queryParams),
    [queryParams, statsQuery.data],
  );
  const events = statsPayload.events;
  const news = statsPayload.news;

  const eventTotals = useMemo(
    () => ({
      total: sumByCount(events.by_date),
      typeCount: events.by_type.length,
      symbolCount: events.by_symbol.length,
    }),
    [events],
  );
  const newsTotals = useMemo(
    () => ({
      total: sumByCount(news.by_date),
      sentimentCount: news.by_sentiment.length,
      symbolCount: news.by_symbol.length,
    }),
    [news],
  );

  const eventDateOption = useMemo(
    () =>
      buildLineOption({
        labels: events.by_date.map((item) => formatDate(item.date)),
        values: events.by_date.map((item) => item.count),
        color: "#2563eb",
        areaColor: "rgba(37, 99, 235, 0.28)",
        title: "Event volume",
      }),
    [events.by_date],
  );
  const eventTypeOption = useMemo(
    () =>
      buildBarOption({
        labels: events.by_type.map((item) => item.type),
        values: events.by_type.map((item) => item.count),
        color: "#0891b2",
        title: "Event type",
      }),
    [events.by_type],
  );
  const eventSymbolOption = useMemo(
    () =>
      buildBarOption({
        labels: events.by_symbol.map((item) => item.symbol),
        values: events.by_symbol.map((item) => item.count),
        color: "#0f766e",
        title: "Event symbol",
      }),
    [events.by_symbol],
  );
  const newsDateOption = useMemo(
    () =>
      buildLineOption({
        labels: news.by_date.map((item) => formatDate(item.date)),
        values: news.by_date.map((item) => item.count),
        color: "#f59e0b",
        areaColor: "rgba(245, 158, 11, 0.3)",
        title: "News volume",
      }),
    [news.by_date],
  );
  const newsSentimentOption = useMemo(
    () =>
      buildBarOption({
        labels: news.by_sentiment.map((item) => item.sentiment),
        values: news.by_sentiment.map((item) => item.count),
        color: "#d97706",
        title: "News sentiment",
      }),
    [news.by_sentiment],
  );
  const newsSymbolOption = useMemo(
    () =>
      buildBarOption({
        labels: news.by_symbol.map((item) => item.symbol),
        values: news.by_symbol.map((item) => item.count),
        color: "#b45309",
        title: "News symbol",
      }),
    [news.by_symbol],
  );

  if (statsQuery.isLoading && !statsQuery.data) {
    return <div className="helper">Loading overview analytics...</div>;
  }

  if (statsQuery.error) {
    return <div className="helper">{`Failed to load overview analytics: ${statsQuery.error.message}`}</div>;
  }

  return (
    <div className="stack-lg">
      <section className="card surface-panel">
        <div className="section-headline" style={{ marginBottom: 12 }}>
          <div>
            <div className="card-title">Analytics Query</div>
            <div className="helper">
              Schema {statsPayload.schema_version} | {statsPayload.query.granularity} |{" "}
              {statsPayload.query.symbols.length ? statsPayload.query.symbols.join(", ") : "all symbols"}
            </div>
          </div>
          <button type="button" className="stock-page-button" onClick={() => statsQuery.refetch()}>
            Refresh
          </button>
        </div>
        <div className="control-bar">
          <label className="field-stack">
            <span>Granularity</span>
            <select className="select" value={granularity} onChange={(event) => setGranularity(event.target.value as StatsOverviewGranularity)}>
              <option value="day">Day</option>
              <option value="week">Week</option>
              <option value="month">Month</option>
            </select>
          </label>
          <label className="field-stack">
            <span>Top Dates</span>
            <input className="input" type="number" min={0} value={topDate} onChange={(event) => setTopDate(Number(event.target.value) || 0)} />
          </label>
          <label className="field-stack">
            <span>Top Types</span>
            <input className="input" type="number" min={0} value={topType} onChange={(event) => setTopType(Number(event.target.value) || 0)} />
          </label>
          <label className="field-stack">
            <span>Top Symbols</span>
            <input className="input" type="number" min={0} value={topSymbol} onChange={(event) => setTopSymbol(Number(event.target.value) || 0)} />
          </label>
          <label className="field-stack">
            <span>Top Sentiments</span>
            <input className="input" type="number" min={0} value={topSentiment} onChange={(event) => setTopSentiment(Number(event.target.value) || 0)} />
          </label>
        </div>
      </section>

      {showEventSection ? (
        <section className="stack-md">
          <div className="section-headline">
            <div>
              <h2 className="section-title" style={{ marginBottom: 0 }}>
                Event Analytics
              </h2>
              <div className="helper">This screen now consumes the explicit dashboard aggregate schema directly.</div>
            </div>
            <span className="kicker">Event</span>
          </div>
          <div className="metric-grid">
            <MetricCard label="Total Events" value={eventTotals.total} helper="Summed from the aggregate series" />
            <MetricCard label="Event Types" value={eventTotals.typeCount} helper="Primary breakdown from the aggregate schema" />
            <MetricCard label="Covered Symbols" value={eventTotals.symbolCount} helper="Distinct symbol buckets returned by the API" />
          </div>
          <div className="grid grid-3">
            <div className="card surface-panel">
              <div className="card-title">By Date</div>
              <ReactECharts option={eventDateOption} style={{ height: 240 }} />
            </div>
            <div className="card surface-panel">
              <div className="card-title">By Type</div>
              <ReactECharts option={eventTypeOption} style={{ height: 240 }} />
            </div>
            <div className="card surface-panel">
              <div className="card-title">By Symbol</div>
              <ReactECharts option={eventSymbolOption} style={{ height: 240 }} />
            </div>
          </div>
          <StatCard<EventDateStat>
            title="Event Series"
            items={events.by_date}
            getLabel={(item) => formatDate(item.date)}
            getCount={(item) => item.count}
          />
          <StatCard<EventTypeStat>
            title="Top Event Types"
            items={events.by_type}
            getLabel={(item) => item.type}
            getCount={(item) => item.count}
          />
          <StatCard<EventSymbolStat>
            title="Top Event Symbols"
            items={events.by_symbol}
            getLabel={(item) => item.symbol}
            getCount={(item) => item.count}
          />
        </section>
      ) : null}

      {showNewsSection ? (
        <section className="stack-md">
          <div className="section-headline">
            <div>
              <h2 className="section-title" style={{ marginBottom: 0 }}>
                News Analytics
              </h2>
              <div className="helper">The page no longer casts this payload to downstream news stats types.</div>
            </div>
            <span className="kicker">News</span>
          </div>
          <div className="metric-grid">
            <MetricCard label="Total News" value={newsTotals.total} helper="Summed from the aggregate series" />
            <MetricCard label="Sentiments" value={newsTotals.sentimentCount} helper="Primary breakdown from the aggregate schema" />
            <MetricCard label="Covered Symbols" value={newsTotals.symbolCount} helper="Distinct symbol buckets returned by the API" />
          </div>
          <div className="grid grid-3">
            <div className="card surface-panel" data-tone="warm">
              <div className="card-title">By Date</div>
              <ReactECharts option={newsDateOption} style={{ height: 240 }} />
            </div>
            <div className="card surface-panel" data-tone="warm">
              <div className="card-title">By Sentiment</div>
              <ReactECharts option={newsSentimentOption} style={{ height: 240 }} />
            </div>
            <div className="card surface-panel" data-tone="warm">
              <div className="card-title">By Symbol</div>
              <ReactECharts option={newsSymbolOption} style={{ height: 240 }} />
            </div>
          </div>
          <StatCard<NewsDateStat>
            title="News Series"
            items={news.by_date}
            getLabel={(item) => formatDate(item.date)}
            getCount={(item) => item.count}
          />
          <StatCard<NewsSentimentStat>
            title="Top Sentiments"
            items={news.by_sentiment}
            getLabel={(item) => item.sentiment}
            getCount={(item) => item.count}
          />
          <StatCard<NewsSymbolStat>
            title="Top News Symbols"
            items={news.by_symbol}
            getLabel={(item) => item.symbol}
            getCount={(item) => item.count}
          />
        </section>
      ) : null}
    </div>
  );
}
