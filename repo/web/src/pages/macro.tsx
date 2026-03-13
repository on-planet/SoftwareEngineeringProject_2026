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
    return <div className="page">宏观指标加载中...</div>;
  }

  if (error) {
    return <div className="page">宏观指标加载失败：{error}</div>;
  }

  return (
    <div className="page">
      <section>
        <h2 className="section-title">宏观指标</h2>
        <div className="toolbar" style={{ marginBottom: 16 }}>
          <span className="helper">选择指标</span>
          <select className="select" value={selectedKey} onChange={(event) => setSelectedKey(event.target.value)}>
            {keys.map((key) => (
              <option key={key} value={key}>
                {key}
              </option>
            ))}
          </select>
        </div>
        <div className="card">
          {seriesLoading ? (
            <div>宏观序列加载中...</div>
          ) : seriesOption ? (
            <ReactECharts option={seriesOption} style={{ height: 320 }} />
          ) : (
            <div>暂无宏观序列数据</div>
          )}
        </div>
      </section>
      <section>
        <h2 className="section-title">最新指标快照</h2>
        <div className="grid grid-3">
          {items.map((item) => (
            <div key={`${item.key}-${item.date}`} className="card">
              <div className="card-title">{item.key}</div>
              <div className="helper">{item.date}</div>
              <div style={{ marginTop: 6 }}>数值 {formatNumber(item.value)}</div>
              <div className="helper" style={{ marginTop: 4 }}>
                评分 {formatNumber(item.score ?? 0)}
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
