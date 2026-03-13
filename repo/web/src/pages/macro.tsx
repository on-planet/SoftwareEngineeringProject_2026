import React, { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";

import { getMacro, getMacroSeries } from "../services/api";
import { formatNumber } from "../utils/format";

type MacroItem = {
  key: string;
  date: string;
  value: number;
  score?: number;
};

type MacroPage = {
  items: MacroItem[];
  total: number;
  limit: number;
  offset: number;
};

type MacroSeries = {
  key: string;
  items: { date: string; value: number; score?: number }[];
};

const DEFAULT_KEY = "CPI";

export default function MacroPage() {
  const [items, setItems] = useState<MacroItem[]>([]);
  const [selectedKey, setSelectedKey] = useState(DEFAULT_KEY);
  const [series, setSeries] = useState<MacroSeries | null>(null);
  const [loading, setLoading] = useState(true);
  const [seriesLoading, setSeriesLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getMacro({ limit: 100 })
      .then((res) => {
        if (!active) return;
        const page = res as MacroPage;
        setItems(page.items ?? []);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) return;
        setError(err.message || "加载宏观指标失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedKey) return;
    let active = true;
    setSeriesLoading(true);
    getMacroSeries(selectedKey)
      .then((res) => {
        if (!active) return;
        setSeries(res as MacroSeries);
      })
      .catch((err: Error) => {
        if (!active) return;
        setError(err.message || "加载宏观序列失败");
      })
      .finally(() => {
        if (active) setSeriesLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedKey]);

  const keys = useMemo(() => Array.from(new Set(items.map((item) => item.key))), [items]);

  const seriesOption = useMemo(() => {
    if (!series) return null;
    const labels = series.items.map((item) => item.date);
    const values = series.items.map((item) => item.value);
    const scores = series.items.map((item) => item.score ?? 0);
    return {
      tooltip: { trigger: "axis" },
      legend: { data: ["数值", "评分"] },
      xAxis: { type: "category", data: labels },
      yAxis: [{ type: "value" }, { type: "value", min: 0, max: 1 }],
      series: [
        { name: "数值", type: "line", data: values, smooth: true },
        { name: "评分", type: "line", yAxisIndex: 1, data: scores, smooth: true },
      ],
    };
  }, [series]);

  if (loading) {
    return <div style={{ padding: 24 }}>宏观指标加载中...</div>;
  }

  if (error) {
    return <div style={{ padding: 24 }}>宏观指标加载失败：{error}</div>;
  }

  return (
    <div style={{ padding: 24 }}>
      <h2 style={{ marginBottom: 16 }}>宏观指标</h2>
      <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 16 }}>
        <span style={{ fontSize: 12, color: "#4a5568" }}>选择指标</span>
        <select value={selectedKey} onChange={(event) => setSelectedKey(event.target.value)}>
          {keys.map((key) => (
            <option key={key} value={key}>
              {key}
            </option>
          ))}
        </select>
      </div>
      {seriesLoading ? (
        <div>宏观序列加载中...</div>
      ) : seriesOption ? (
        <ReactECharts option={seriesOption} style={{ height: 320 }} />
      ) : (
        <div>暂无宏观序列数据</div>
      )}
      <div style={{ marginTop: 24, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: 12 }}>
        {items.map((item) => (
          <div key={`${item.key}-${item.date}`} style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 12 }}>
            <div style={{ fontWeight: 600 }}>{item.key}</div>
            <div style={{ fontSize: 12, color: "#718096" }}>{item.date}</div>
            <div style={{ marginTop: 6 }}>数值 {formatNumber(item.value)}</div>
            <div style={{ marginTop: 4, fontSize: 12 }}>评分 {formatNumber(item.score ?? 0)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
