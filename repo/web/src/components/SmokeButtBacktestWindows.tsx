import React from "react";
import ReactECharts from "echarts-for-react";

import { SmokeButtBacktestResponse, SmokeButtBacktestWindow } from "../services/api";
import { formatPercent } from "../utils/format";

const BUCKET_COLORS = ["#b42318", "#f79009", "#2563eb", "#12b76a", "#475467"];

function formatPercentValue(value?: number | null, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return formatPercent(value, digits);
}

function buildCurveOption(window: SmokeButtBacktestWindow) {
  const dateKeys = Array.from(
    new Set(window.buckets.flatMap((bucket) => bucket.curve.map((point) => point.date))),
  ).sort((left, right) => new Date(left).getTime() - new Date(right).getTime());
  if (!dateKeys.length) {
    return null;
  }
  return {
    color: BUCKET_COLORS,
    tooltip: {
      trigger: "axis",
      valueFormatter: (value: number) => formatPercentValue(value, 2),
    },
    legend: {
      data: window.buckets.map((bucket) => bucket.label),
      top: 0,
    },
    grid: { left: 44, right: 24, top: 48, bottom: 36 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: dateKeys.map((item) => new Date(item).toLocaleDateString("zh-CN")),
    },
    yAxis: {
      type: "value",
      axisLabel: {
        formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
      },
    },
    series: window.buckets.map((bucket) => {
      const valueMap = new Map(bucket.curve.map((point) => [point.date, point.cumulative_return ?? null]));
      return {
        name: bucket.label,
        type: "line",
        smooth: true,
        showSymbol: false,
        data: dateKeys.map((dateKey) => valueMap.get(dateKey) ?? null),
      };
    }),
  };
}

function buildBarOption(window: SmokeButtBacktestWindow) {
  if (!window.buckets.length) {
    return null;
  }
  return {
    color: ["#2563eb", "#b42318"],
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (value: number) => formatPercentValue(value, 2),
    },
    legend: {
      data: ["平均收益", "最大回撤"],
      top: 0,
    },
    grid: { left: 44, right: 24, top: 48, bottom: 36 },
    xAxis: {
      type: "category",
      data: window.buckets.map((bucket) => bucket.label),
    },
    yAxis: {
      type: "value",
      axisLabel: {
        formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
      },
    },
    series: [
      {
        name: "平均收益",
        type: "bar",
        barMaxWidth: 28,
        data: window.buckets.map((bucket) => bucket.avg_return ?? null),
      },
      {
        name: "最大回撤",
        type: "bar",
        barMaxWidth: 28,
        data: window.buckets.map((bucket) => bucket.max_drawdown ?? null),
      },
    ],
  };
}

type SmokeButtBacktestWindowsProps = {
  payload: SmokeButtBacktestResponse;
};

export function SmokeButtBacktestWindows({ payload }: SmokeButtBacktestWindowsProps) {
  if (!payload) {
    return null;
  }

  return (
    <>
      {payload.windows.map((window) => {
        const curveOption = buildCurveOption(window);
        const barOption = buildBarOption(window);
        return (
          <div key={window.horizon_days} className="strategy-feature-card">
            <div className="page-header" style={{ marginBottom: 12 }}>
              <div>
                <div className="card-title">{window.horizon_days} 交易日策略复盘</div>
                <div className="helper">
                  每 {window.rebalance_step} 个交易日调仓一次，按评分分成 {payload.bucket_count} 组。
                </div>
              </div>
              <div className="helper">
                Top/Bottom 利差 {formatPercentValue(window.summary.spread_return, 2)} | 单调性{" "}
                {formatPercentValue(window.summary.monotonicity, 0)}
              </div>
            </div>

            <div className="depth-grid" style={{ marginTop: 0 }}>
              <div className="depth-card">
                <div className="card-title">累计收益曲线</div>
                {curveOption ? <ReactECharts option={curveOption} style={{ height: 300 }} /> : <div className="helper">暂无曲线数据</div>}
              </div>
              <div className="depth-card">
                <div className="card-title">分组收益与回撤</div>
                {barOption ? <ReactECharts option={barOption} style={{ height: 300 }} /> : <div className="helper">暂无分组统计</div>}
              </div>
            </div>

            <div style={{ overflowX: "auto", marginTop: 16 }}>
              <table className="data-table dense-table">
                <thead>
                  <tr>
                    <th>评分组</th>
                    <th>平均收益</th>
                    <th>胜率</th>
                    <th>最大回撤</th>
                    <th>预测均值</th>
                    <th>样本数</th>
                    <th>周期数</th>
                  </tr>
                </thead>
                <tbody>
                  {window.buckets.map((bucket) => (
                    <tr key={`${window.horizon_days}-${bucket.bucket}`}>
                      <td>{bucket.label}</td>
                      <td>{formatPercentValue(bucket.avg_return, 2)}</td>
                      <td>{formatPercentValue(bucket.win_rate, 0)}</td>
                      <td>{formatPercentValue(bucket.max_drawdown, 2)}</td>
                      <td>{formatPercentValue(bucket.avg_predicted_return, 2)}</td>
                      <td>{bucket.sample_count}</td>
                      <td>{bucket.period_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}
    </>
  );
}
