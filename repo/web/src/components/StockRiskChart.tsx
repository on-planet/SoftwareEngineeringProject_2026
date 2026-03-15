import React, { useEffect, useMemo, useState } from "react";

import ReactECharts from "echarts-for-react";

import { getRisk, getRiskSeries } from "../services/api";
import { formatPercent } from "../utils/format";

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
        setError(err.message || "风险指标加载失败");
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
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12, gap: 12, flexWrap: "wrap" }}>
        <div style={{ fontWeight: 600 }}>风险序列</div>
        <div style={{ display: "flex", gap: 12, fontSize: 12, color: "#718096", flexWrap: "wrap" }}>
          <span>缓存：{cacheHitLabel}</span>
          {snapshot?.as_of ? <span>截至：{new Date(snapshot.as_of).toLocaleDateString("zh-CN")}</span> : null}
        </div>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        <input
          className="input"
          type="number"
          min={2}
          max={200}
          value={windowSize}
          onChange={(event) => setWindowSize(Number(event.target.value) || 20)}
          placeholder="窗口"
          style={{ width: 110 }}
        />
        <input
          className="input"
          type="number"
          min={20}
          max={500}
          value={limit}
          onChange={(event) => setLimit(Number(event.target.value) || 200)}
          placeholder="条数"
          style={{ width: 110 }}
        />
        <input className="input" type="date" value={start} onChange={(event) => setStart(event.target.value)} />
        <input className="input" type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
      </div>
      {loading ? (
        <div className="helper">风险指标加载中...</div>
      ) : error ? (
        <div className="helper">风险指标加载失败：{error}</div>
      ) : series.length ? (
        <ReactECharts option={chartOption} style={{ height: 240 }} />
      ) : (
        <div className="helper">暂无风险序列数据。</div>
      )}
      {snapshot ? (
        <div className="helper" style={{ marginTop: 12 }}>
          最大回撤：{snapshot.max_drawdown !== null && snapshot.max_drawdown !== undefined ? formatPercent(snapshot.max_drawdown) : "--"}
          <span style={{ marginLeft: 12 }}>
            波动率：{snapshot.volatility !== null && snapshot.volatility !== undefined ? formatPercent(snapshot.volatility) : "--"}
          </span>
        </div>
      ) : null}
    </div>
  );
}
