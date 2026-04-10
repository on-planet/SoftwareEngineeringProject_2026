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
        <div className="helper">暂无数据。</div>
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
        title: "事件数量",
      }),
    [events.by_date],
  );
  const eventTypeOption = useMemo(
    () =>
      buildBarOption({
        labels: events.by_type.map((item) => item.type),
        values: events.by_type.map((item) => item.count),
        color: "#0891b2",
        title: "事件类型",
      }),
    [events.by_type],
  );
  const eventSymbolOption = useMemo(
    () =>
      buildBarOption({
        labels: events.by_symbol.map((item) => item.symbol),
        values: events.by_symbol.map((item) => item.count),
        color: "#0f766e",
        title: "事件标的",
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
        title: "新闻数量",
      }),
    [news.by_date],
  );
  const newsSentimentOption = useMemo(
    () =>
      buildBarOption({
        labels: news.by_sentiment.map((item) => item.sentiment),
        values: news.by_sentiment.map((item) => item.count),
        color: "#d97706",
        title: "情感分布",
      }),
    [news.by_sentiment],
  );
  const newsSymbolOption = useMemo(
    () =>
      buildBarOption({
        labels: news.by_symbol.map((item) => item.symbol),
        values: news.by_symbol.map((item) => item.count),
        color: "#b45309",
        title: "新闻标的",
      }),
    [news.by_symbol],
  );

  if (statsQuery.isLoading && !statsQuery.data) {
    return <div className="helper">统计概览加载中...</div>;
  }

  if (statsQuery.error) {
    return <div className="helper">{`统计概览加载失败：${statsQuery.error.message}`}</div>;
  }

  return (
    <div className="stack-lg">
      <section className="card surface-panel">
        <div className="section-headline" style={{ marginBottom: 12 }}>
          <div>
            <div className="card-title">查询参数</div>
            <div className="helper">
              版本 {statsPayload.schema_version} | {statsPayload.query.granularity === "day" ? "日度" : statsPayload.query.granularity === "week" ? "周度" : "月度"} |{" "}
              {statsPayload.query.symbols.length ? statsPayload.query.symbols.join(", ") : "全部标的"}
            </div>
          </div>
          <button type="button" className="stock-page-button" onClick={() => statsQuery.refetch()}>
            刷新
          </button>
        </div>
        <div className="control-bar">
          <label className="field-stack">
            <span>粒度</span>
            <select className="select" value={granularity} onChange={(event) => setGranularity(event.target.value as StatsOverviewGranularity)}>
              <option value="day">日度</option>
              <option value="week">周度</option>
              <option value="month">月度</option>
            </select>
          </label>
          <label className="field-stack">
            <span>日期条数</span>
            <input className="input" type="number" min={0} value={topDate} onChange={(event) => setTopDate(Number(event.target.value) || 0)} />
          </label>
          <label className="field-stack">
            <span>类型条数</span>
            <input className="input" type="number" min={0} value={topType} onChange={(event) => setTopType(Number(event.target.value) || 0)} />
          </label>
          <label className="field-stack">
            <span>标的条数</span>
            <input className="input" type="number" min={0} value={topSymbol} onChange={(event) => setTopSymbol(Number(event.target.value) || 0)} />
          </label>
          <label className="field-stack">
            <span>情感条数</span>
            <input className="input" type="number" min={0} value={topSentiment} onChange={(event) => setTopSentiment(Number(event.target.value) || 0)} />
          </label>
        </div>
      </section>

      {showEventSection ? (
        <section className="stack-md">
          <div className="section-headline">
            <div>
              <h2 className="section-title" style={{ marginBottom: 0 }}>
                事件统计
              </h2>
              <div className="helper">基于仪表盘聚合数据模式实时计算。</div>
            </div>
            <span className="kicker">事件</span>
          </div>
          <div className="metric-grid">
            <MetricCard label="事件总数" value={eventTotals.total} helper="聚合序列汇总" />
            <MetricCard label="事件类型" value={eventTotals.typeCount} helper="聚合模式主分类" />
            <MetricCard label="覆盖标的" value={eventTotals.symbolCount} helper="API 返回的不同标的分组数" />
          </div>
          <div className="grid grid-3">
            <div className="card surface-panel">
              <div className="card-title">按日期分布</div>
              <ReactECharts option={eventDateOption} style={{ height: 240 }} />
            </div>
            <div className="card surface-panel">
              <div className="card-title">按类型分布</div>
              <ReactECharts option={eventTypeOption} style={{ height: 240 }} />
            </div>
            <div className="card surface-panel">
              <div className="card-title">按标的分布</div>
              <ReactECharts option={eventSymbolOption} style={{ height: 240 }} />
            </div>
          </div>
          <StatCard<EventDateStat>
            title="事件序列"
            items={events.by_date}
            getLabel={(item) => formatDate(item.date)}
            getCount={(item) => item.count}
          />
          <StatCard<EventTypeStat>
            title="热门事件类型"
            items={events.by_type}
            getLabel={(item) => item.type}
            getCount={(item) => item.count}
          />
          <StatCard<EventSymbolStat>
            title="热门事件标的"
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
                新闻统计
              </h2>
              <div className="helper">基于仪表盘聚合数据模式实时计算。</div>
            </div>
            <span className="kicker">新闻</span>
          </div>
          <div className="metric-grid">
            <MetricCard label="新闻总数" value={newsTotals.total} helper="聚合序列汇总" />
            <MetricCard label="情感类别" value={newsTotals.sentimentCount} helper="聚合模式主分类" />
            <MetricCard label="覆盖标的" value={newsTotals.symbolCount} helper="API 返回的不同标的分组数" />
          </div>
          <div className="grid grid-3">
            <div className="card surface-panel" data-tone="warm">
              <div className="card-title">按日期分布</div>
              <ReactECharts option={newsDateOption} style={{ height: 240 }} />
            </div>
            <div className="card surface-panel" data-tone="warm">
              <div className="card-title">按情感分布</div>
              <ReactECharts option={newsSentimentOption} style={{ height: 240 }} />
            </div>
            <div className="card surface-panel" data-tone="warm">
              <div className="card-title">按标的分布</div>
              <ReactECharts option={newsSymbolOption} style={{ height: 240 }} />
            </div>
          </div>
          <StatCard<NewsDateStat>
            title="新闻序列"
            items={news.by_date}
            getLabel={(item) => formatDate(item.date)}
            getCount={(item) => item.count}
          />
          <StatCard<NewsSentimentStat>
            title="热门情感"
            items={news.by_sentiment}
            getLabel={(item) => item.sentiment}
            getCount={(item) => item.count}
          />
          <StatCard<NewsSymbolStat>
            title="热门新闻标的"
            items={news.by_symbol}
            getLabel={(item) => item.symbol}
            getCount={(item) => item.count}
          />
        </section>
      ) : null}
    </div>
  );
}
