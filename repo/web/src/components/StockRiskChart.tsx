import React, { useEffect, useMemo, useState } from "react";

import ReactECharts from "echarts-for-react";

import { getRisk, getRiskSeries } from "../services/api";

type RiskSnapshot = {
  symbol: string;
  max_drawdown: number | null;
  volatility: number | null;
  as_of: string | null;
  cache_hit?: boolean;
};

type RiskPoint = {
  date: string;
  max_drawdown: number;
  volatility: number;
};

type RiskSeriesResponse = {
  symbol: string;
  items: RiskPoint[];
  cache_hit?: boolean;
};

type Props = {
  symbol: string;
};

export function StockRiskChart({ symbol }: Props) {
  const [snapshot, setSnapshot] = useState<RiskSnapshot | null>(null);
  const [series, setSeries] = useState<RiskPoint[]>([]);
  const [seriesCacheHit, setSeriesCacheHit] = useState<boolean | undefined>(undefined);
  const [windowSize, setWindowSize] = useState(20);
  const [limit, setLimit] = useState(200);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([
      getRisk(symbol),
      getRiskSeries(symbol, {
        window: windowSize,
        limit,
        start: start || undefined,
        end: end || undefined,
      }),
    ])
      .then(([riskRes, seriesRes]) => {
        if (!active) {
          return;
        }
        const snapshotPayload = riskRes as RiskSnapshot;
        const seriesPayload = seriesRes as RiskSeriesResponse;
        setSnapshot(snapshotPayload);
        setSeries(seriesPayload.items ?? []);
        setSeriesCacheHit(seriesPayload.cache_hit);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setError(err.message || "加载风险指标失败");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [symbol, windowSize, limit, start, end]);

  const chartOption = useMemo(() => {
    const labels = series.map((item) => new Date(item.date).toLocaleDateString("zh-CN"));
    const maxDrawdown = series.map((item) => item.max_drawdown);
    const volatility = series.map((item) => item.volatility);
    return {
      tooltip: { trigger: "axis" },
      legend: { data: ["最大回撤", "波动率"] },
      xAxis: { type: "category", data: labels, boundaryGap: false },
      yAxis: { type: "value" },
      series: [
        { name: "最大回撤", type: "line", data: maxDrawdown, smooth: true },
        { name: "波动率", type: "line", data: volatility, smooth: true },
      ],
      grid: { left: 40, right: 20, top: 40, bottom: 40 },
    };
  }, [series]);

  const cacheHitLabel = seriesCacheHit === undefined ? "未知" : seriesCacheHit ? "命中" : "未命中";

  return (
    <div style={{ border: "1px solid #e2e8f0", borderRadius: 8, padding: 16, background: "#fff" }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12, gap: 12, flexWrap: "wrap" }}>
        <div style={{ fontWeight: 600 }}>风险指标</div>
        <div style={{ display: "flex", gap: 12, fontSize: 12, color: "#718096" }}>
          <span>缓存：{cacheHitLabel}</span>
          {snapshot?.as_of ? <span>截止 {new Date(snapshot.as_of).toLocaleDateString("zh-CN")}</span> : null}
        </div>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
          窗口
          <input
            type="number"
            min={2}
            max={200}
            value={windowSize}
            onChange={(event) => setWindowSize(Number(event.target.value) || 20)}
            style={{ width: 90, padding: "4px 8px" }}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
          最大条数
          <input
            type="number"
            min={20}
            max={500}
            value={limit}
            onChange={(event) => setLimit(Number(event.target.value) || 200)}
            style={{ width: 90, padding: "4px 8px" }}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
          起始日期
          <input
            type="date"
            value={start}
            onChange={(event) => setStart(event.target.value)}
            style={{ padding: "4px 8px" }}
          />
        </label>
        <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
          截止日期
          <input
            type="date"
            value={end}
            onChange={(event) => setEnd(event.target.value)}
            style={{ padding: "4px 8px" }}
          />
        </label>
      </div>
      {loading ? (
        <div>风险指标加载中...</div>
      ) : error ? (
        <div>风险指标加载失败：{error}</div>
      ) : (
        <ReactECharts option={chartOption} style={{ height: 240 }} />
      )}
      {snapshot ? (
        <div style={{ marginTop: 8, fontSize: 12, color: "#4a5568" }}>
          最大回撤：{snapshot.max_drawdown ?? "-"} · 波动率：{snapshot.volatility ?? "-"}
        </div>
      ) : null}
    </div>
  );
}
