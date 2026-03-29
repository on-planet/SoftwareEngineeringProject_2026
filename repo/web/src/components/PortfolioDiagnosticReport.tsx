import React, { useMemo } from "react";

import ReactECharts from "echarts-for-react";

import { AnimatedNumber } from "./motion/AnimatedNumber";
import {
  PortfolioTargetScope,
  buildPortfolioDiagnosticsQueryKey,
  getPortfolioDiagnosticsQueryOptions,
  loadPortfolioDiagnostics,
} from "../domain/portfolioDiagnostics";
import { useApiQuery } from "../hooks/useApiQuery";
import { useAuth } from "../providers/AuthProvider";
import { PortfolioDiagnosticsResponse } from "../services/api";
import { formatPercent } from "../utils/format";


function formatMoney(value?: number | null, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return Number(value).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}


function pillTone(tone: string) {
  if (tone === "risk") {
    return "negative";
  }
  if (tone === "positive") {
    return "positive";
  }
  return "neutral";
}


function barColor(value: number) {
  if (value >= 0.45) {
    return "#1d4ed8";
  }
  if (value >= 0.22) {
    return "#0f766e";
  }
  return "#94a3b8";
}


function sensitivityColor(value: number) {
  if (value >= 0) {
    return "#027a48";
  }
  return "#b42318";
}


function buildSensitivityOption(payload: PortfolioDiagnosticsResponse) {
  if (!payload.macro_sensitivities.length) {
    return null;
  }
  return {
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (value: number) => formatPercent(value, 2),
    },
    grid: { left: 52, right: 20, top: 20, bottom: 36 },
    xAxis: {
      type: "value",
      axisLabel: {
        formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
      },
    },
    yAxis: {
      type: "category",
      data: payload.macro_sensitivities.map((item) => item.label),
    },
    series: [
      {
        type: "bar",
        barMaxWidth: 24,
        data: payload.macro_sensitivities.map((item) => ({
          value: item.portfolio_change_pct,
          itemStyle: {
            color: sensitivityColor(item.portfolio_change_pct),
          },
        })),
      },
    ],
  };
}

type PortfolioDiagnosticReportProps = {
  targetType?: PortfolioTargetScope;
};

export function PortfolioDiagnosticReport({
  targetType = "bought",
}: PortfolioDiagnosticReportProps) {
  const { token, isAuthenticated } = useAuth();
  const isWatch = targetType === "watch";
  const title = isWatch ? "观察标的诊断报告" : "组合诊断报告";
  const loadingText = isWatch ? "观察标的诊断报告加载中..." : "组合诊断报告加载中...";
  const errorPrefix = isWatch ? "观察标的诊断报告加载失败" : "组合诊断报告加载失败";
  const emptyTitle = isWatch ? "暂无观察标的诊断报告" : "暂无组合诊断报告";
  const emptyText = isWatch
    ? "先添加至少一个观察标的，系统会按等权观察篮子生成画像和宏观敏感度。"
    : "先录入至少一笔已买标的，系统才会生成组合画像和宏观敏感度。";
  const heroDescription = isWatch
    ? "基于观察标的等权篮子的行业结构、风格暴露和宏观情景敏感度，自动生成观察画像和解释层。"
    : "基于已买组合的行业结构、风格暴露和宏观情景敏感度，自动生成组合画像和解释层。";
  const diagnosticsQuery = useApiQuery<PortfolioDiagnosticsResponse>(
    isAuthenticated && token ? buildPortfolioDiagnosticsQueryKey(token, targetType) : null,
    () => loadPortfolioDiagnostics(token || "", targetType),
    getPortfolioDiagnosticsQueryOptions(targetType),
  );

  const payload = diagnosticsQuery.data;
  const sensitivityOption = useMemo(
    () => (payload ? buildSensitivityOption(payload) : null),
    [payload],
  );

  if (!isAuthenticated || !token) {
    return null;
  }

  if (diagnosticsQuery.isLoading && !payload) {
    return <div className="helper">{loadingText}</div>;
  }

  if (diagnosticsQuery.error) {
    return <div className="helper">{`${errorPrefix}：${diagnosticsQuery.error.message}`}</div>;
  }

  if (!payload || payload.summary.holdings_count === 0) {
    return (
      <div className="surface-empty">
        <strong>{emptyTitle}</strong>
        <div className="helper">{emptyText}</div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <section className="strategy-feature-card">
        <div className="page-header" style={{ marginBottom: 12 }}>
          <div>
            <div className="card-title">{title}</div>
            <div className="helper">{heroDescription}</div>
          </div>
          <span className="strategy-pill" data-tone="neutral">
            {payload.schema_version}
          </span>
        </div>

        <div className="hero-grid">
          <div className="summary-card">
            <div className="card-title">{isWatch ? "观察标的数" : "组合市值"}</div>
            <div className="stock-score-value">
              <AnimatedNumber
                value={isWatch ? payload.summary.holdings_count : payload.summary.total_value}
                formatter={(value) => (isWatch ? String(Math.round(value)) : formatMoney(value, 0))}
              />
            </div>
            <div className="helper">{isWatch ? "按等权观察篮子估算" : `${payload.summary.holdings_count} 个持仓`}</div>
          </div>
          <div className="summary-card">
            <div className="card-title">{isWatch ? "覆盖行业" : "累计盈亏"}</div>
            {isWatch ? (
              <>
                <div className="stock-score-value">
                  <AnimatedNumber value={payload.summary.sector_count} formatter={(value) => String(Math.round(value))} />
                </div>
                <div className="helper">行业分布与风格画像</div>
              </>
            ) : (
              <>
                <div
                  className="stock-score-value"
                  style={{ color: payload.summary.total_pnl < 0 ? "#b42318" : "#027a48" }}
                >
                  <AnimatedNumber value={payload.summary.total_pnl} formatter={(value) => formatMoney(value, 0)} />
                </div>
                <div className="helper">{formatPercent(payload.summary.total_pnl_pct, 2)}</div>
              </>
            )}
          </div>
          <div className="summary-card">
            <div className="card-title">主导行业</div>
            <div className="stock-score-value" style={{ fontSize: 24 }}>{payload.summary.top_sector ?? "--"}</div>
            <div className="helper">{`${payload.summary.sector_count} 个行业`}</div>
          </div>
          <div className="summary-card">
            <div className="card-title">前三大集中度</div>
            <div className="stock-score-value">
              <AnimatedNumber value={payload.summary.top3_weight} formatter={(value) => formatPercent(value, 0)} />
            </div>
            <div className="helper">{payload.summary.top_market ? `主市场 ${payload.summary.top_market}` : "市场分布"}</div>
          </div>
        </div>

        <div className="strategy-pill-row" style={{ marginTop: 16 }}>
          {payload.portrait.map((item) => (
            <span key={item.code} className="strategy-pill" data-tone={pillTone(item.tone)}>
              {item.label}
            </span>
          ))}
        </div>

        <div
          style={{
            marginTop: 12,
            border: "1px solid rgba(15, 23, 42, 0.08)",
            borderRadius: 16,
            padding: 14,
            background: "rgba(255, 255, 255, 0.84)",
          }}
        >
          <div className="card-title">报告摘要</div>
          <div className="helper" style={{ marginTop: 8 }}>
            {payload.overview}
          </div>
        </div>
      </section>

      <div className="depth-grid" style={{ marginTop: 0 }}>
        <div className="depth-card">
          <div className="card-title">风格暴露</div>
          <div style={{ display: "grid", gap: 12, marginTop: 14 }}>
            {payload.style_exposures.map((item) => (
              <div key={item.code} style={{ display: "grid", gap: 6 }}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <span style={{ fontWeight: 700 }}>{item.label}</span>
                  <span className="helper">{formatPercent(item.score, 0)}</span>
                </div>
                <div
                  style={{
                    height: 10,
                    borderRadius: 999,
                    background: "rgba(148, 163, 184, 0.16)",
                    overflow: "hidden",
                  }}
                >
                  <div
                    style={{
                      width: `${Math.max(6, Math.min(100, item.score * 100))}%`,
                      height: "100%",
                      borderRadius: 999,
                      background: barColor(item.score),
                    }}
                  />
                </div>
                <div className="helper">{item.explanation}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="depth-card">
          <div className="card-title">宏观敏感度</div>
          {sensitivityOption ? (
            <ReactECharts option={sensitivityOption} style={{ height: 260, marginTop: 10 }} />
          ) : (
            <div className="helper">暂无宏观敏感度数据。</div>
          )}
          <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
            {payload.macro_sensitivities.map((item) => (
              <div key={item.code}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <span style={{ fontWeight: 700 }}>{item.label}</span>
                  <span style={{ color: sensitivityColor(item.portfolio_change_pct), fontWeight: 700 }}>
                    {item.portfolio_change_pct >= 0 ? "+" : ""}
                    {formatPercent(item.portfolio_change_pct, 2)}
                  </span>
                </div>
                <div className="helper" style={{ marginTop: 4 }}>
                  {item.explanation}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="depth-grid" style={{ marginTop: 0 }}>
        <div className="depth-card">
          <div className="card-title">行业暴露</div>
          <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
            {payload.sector_exposure.map((item) => (
              <div key={item.label}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <span style={{ fontWeight: 700 }}>{item.label}</span>
                  <span className="helper">{`${formatMoney(item.value, 0)} / ${formatPercent(item.weight, 0)}`}</span>
                </div>
                <div
                  style={{
                    height: 10,
                    borderRadius: 999,
                    background: "rgba(37, 99, 235, 0.12)",
                    overflow: "hidden",
                    marginTop: 6,
                  }}
                >
                  <div
                    style={{
                      width: `${Math.max(6, Math.min(100, item.weight * 100))}%`,
                      height: "100%",
                      borderRadius: 999,
                      background: "#2563eb",
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="depth-card">
          <div className="card-title">市场暴露</div>
          <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
            {payload.market_exposure.map((item) => (
              <div key={item.label}>
                <div style={{ display: "flex", justifyContent: "space-between", gap: 12 }}>
                  <span style={{ fontWeight: 700 }}>{item.label}</span>
                  <span className="helper">{`${formatMoney(item.value, 0)} / ${formatPercent(item.weight, 0)}`}</span>
                </div>
                <div
                  style={{
                    height: 10,
                    borderRadius: 999,
                    background: "rgba(245, 158, 11, 0.16)",
                    overflow: "hidden",
                    marginTop: 6,
                  }}
                >
                  <div
                    style={{
                      width: `${Math.max(6, Math.min(100, item.weight * 100))}%`,
                      height: "100%",
                      borderRadius: 999,
                      background: "#f59e0b",
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <section className="card">
        <div className="card-title">{isWatch ? "前几大观察标的画像" : "前几大持仓画像"}</div>
        {isWatch ? (
          <div className="helper" style={{ marginTop: 8 }}>
            观察标的按等权篮子估算，重点用于识别风格、行业和宏观敏感度，不展示真实持仓盈亏。
          </div>
        ) : null}
        <div style={{ overflowX: "auto", marginTop: 12 }}>
          <table className="data-table dense-table">
            <thead>
              <tr>
                <th>股票</th>
                <th>市场</th>
                <th>行业</th>
                <th>组合权重</th>
                {isWatch ? null : <th>当前市值</th>}
                {isWatch ? null : <th>累计盈亏</th>}
                {isWatch ? null : <th>累计收益率</th>}
              </tr>
            </thead>
            <tbody>
              {payload.top_positions.map((item) => (
                <tr key={item.symbol}>
                  <td>{`${item.symbol} ${item.name}`}</td>
                  <td>{item.market || "--"}</td>
                  <td>{item.sector || "--"}</td>
                  <td>{formatPercent(item.weight, 2)}</td>
                  {isWatch ? null : <td>{formatMoney(item.current_value, 0)}</td>}
                  {isWatch ? null : (
                    <td style={{ color: item.pnl_value < 0 ? "#b42318" : "#027a48" }}>
                      {formatMoney(item.pnl_value, 0)}
                    </td>
                  )}
                  {isWatch ? null : (
                    <td style={{ color: item.pnl_pct < 0 ? "#b42318" : "#027a48" }}>
                      {formatPercent(item.pnl_pct, 2)}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
