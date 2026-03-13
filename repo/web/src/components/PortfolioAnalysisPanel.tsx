import React, { useEffect, useMemo, useState } from "react";

import ReactECharts from "echarts-for-react";

import { getPortfolioAnalysis, getSectorExposure } from "../services/api";
import { formatNumber, formatPercent } from "../utils/format";

type SectorExposureItem = {
  sector: string;
  value: number;
  weight: number;
};

type SectorExposureResponse = {
  market?: string | null;
  items: SectorExposureItem[];
};

type PortfolioItem = {
  symbol: string;
  shares: number;
  avg_cost: number;
  latest_price: number;
  pnl: number;
  pnl_pct: number;
  sector?: string | null;
};

type PortfolioSummary = {
  total_cost: number;
  total_value: number;
  total_pnl: number;
  total_pnl_pct: number;
};

type PortfolioExposure = {
  sector: string;
  value: number;
  weight: number;
};

type PortfolioHolding = {
  symbol: string;
  value: number;
  weight: number;
};

type PortfolioAnalysisResponse = {
  user_id: number;
  items: PortfolioItem[];
  summary: PortfolioSummary;
  sector_exposure: PortfolioExposure[];
  top_holdings: PortfolioHolding[];
};

const DEFAULT_USER_ID = 1;

export function PortfolioAnalysisPanel() {
  const [userId, setUserId] = useState(DEFAULT_USER_ID);
  const [topN, setTopN] = useState(5);
  const [market, setMarket] = useState("");
  const [asOf, setAsOf] = useState("");
  const [analysis, setAnalysis] = useState<PortfolioAnalysisResponse | null>(null);
  const [sectorExposure, setSectorExposure] = useState<SectorExposureItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([
      getPortfolioAnalysis(userId, { top_n: topN }),
      getSectorExposure({ market: market || undefined, as_of: asOf || undefined, limit: 50 }),
    ])
      .then(([analysisRes, sectorRes]) => {
        if (!active) return;
        setAnalysis(analysisRes as PortfolioAnalysisResponse);
        const exposurePayload = sectorRes as SectorExposureResponse;
        setSectorExposure(exposurePayload.items ?? []);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) return;
        setError(err.message || "加载组合分析失败");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [userId, topN, market, asOf]);

  const sectorPieOption = useMemo(() => {
    if (!analysis) return null;
    const data = analysis.sector_exposure.map((item) => ({ name: item.sector, value: item.value }));
    return {
      tooltip: { trigger: "item" },
      legend: { bottom: 0 },
      series: [
        {
          name: "组合行业",
          type: "pie",
          radius: ["35%", "65%"],
          data,
        },
      ],
    };
  }, [analysis]);

  const holdingsBarOption = useMemo(() => {
    if (!analysis) return null;
    const labels = analysis.top_holdings.map((item) => item.symbol);
    const values = analysis.top_holdings.map((item) => item.value);
    return {
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: labels },
      yAxis: { type: "value" },
      series: [{ type: "bar", data: values, barMaxWidth: 36 }],
      grid: { left: 40, right: 20, top: 30, bottom: 40 },
    };
  }, [analysis]);

  const sectorExposureOption = useMemo(() => {
    if (sectorExposure.length === 0) return null;
    const labels = sectorExposure.map((item) => item.sector);
    const values = sectorExposure.map((item) => item.value);
    return {
      tooltip: { trigger: "axis" },
      xAxis: { type: "category", data: labels },
      yAxis: { type: "value" },
      series: [{ type: "bar", data: values, barMaxWidth: 36 }],
      grid: { left: 40, right: 20, top: 30, bottom: 40 },
    };
  }, [sectorExposure]);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <section
        style={{
          border: "1px solid #edf2f7",
          borderRadius: 12,
          padding: 16,
          background: "#f8fafc",
        }}
      >
        <div style={{ fontWeight: 600, marginBottom: 12 }}>组合分析筛选</div>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            用户ID
            <input
              type="number"
              min={1}
              value={userId}
              onChange={(event) => setUserId(Number(event.target.value) || DEFAULT_USER_ID)}
              style={{ padding: "6px 8px" }}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            TopN
            <input
              type="number"
              min={1}
              max={50}
              value={topN}
              onChange={(event) => setTopN(Number(event.target.value) || 5)}
              style={{ padding: "6px 8px" }}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            行业市场
            <select value={market} onChange={(event) => setMarket(event.target.value)} style={{ padding: "6px 8px" }}>
              <option value="">全部市场</option>
              <option value="A">A股</option>
              <option value="HK">港股</option>
            </select>
          </label>
          <label style={{ display: "flex", flexDirection: "column", fontSize: 12, gap: 6 }}>
            行业日期
            <input
              type="date"
              value={asOf}
              onChange={(event) => setAsOf(event.target.value)}
              style={{ padding: "6px 8px" }}
            />
          </label>
        </div>
      </section>

      {loading ? (
        <div>组合分析加载中...</div>
      ) : error ? (
        <div>组合分析加载失败：{error}</div>
      ) : analysis ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <section style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))" }}>
            <div style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, background: "#fff" }}>
              <div style={{ fontSize: 12, color: "#718096" }}>组合成本</div>
              <div style={{ fontWeight: 600, marginTop: 4 }}>{formatNumber(analysis.summary.total_cost)}</div>
            </div>
            <div style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, background: "#fff" }}>
              <div style={{ fontSize: 12, color: "#718096" }}>组合市值</div>
              <div style={{ fontWeight: 600, marginTop: 4 }}>{formatNumber(analysis.summary.total_value)}</div>
            </div>
            <div style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, background: "#fff" }}>
              <div style={{ fontSize: 12, color: "#718096" }}>浮动收益</div>
              <div style={{ fontWeight: 600, marginTop: 4 }}>{formatNumber(analysis.summary.total_pnl)}</div>
            </div>
            <div style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, background: "#fff" }}>
              <div style={{ fontSize: 12, color: "#718096" }}>收益率</div>
              <div style={{ fontWeight: 600, marginTop: 4 }}>{formatPercent(analysis.summary.total_pnl_pct)}</div>
            </div>
          </section>

          <section style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))" }}>
            <div style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, background: "#fff" }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>组合行业暴露</div>
              {sectorPieOption ? <ReactECharts option={sectorPieOption} style={{ height: 240 }} /> : <div>暂无行业暴露</div>}
            </div>
            <div style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, background: "#fff" }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>集中度 Top 持仓</div>
              {holdingsBarOption ? <ReactECharts option={holdingsBarOption} style={{ height: 240 }} /> : <div>暂无持仓数据</div>}
            </div>
            <div style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, background: "#fff" }}>
              <div style={{ fontWeight: 600, marginBottom: 8 }}>市场行业暴露</div>
              {sectorExposureOption ? <ReactECharts option={sectorExposureOption} style={{ height: 240 }} /> : <div>暂无行业暴露数据</div>}
            </div>
          </section>

          <section style={{ border: "1px solid #e2e8f0", borderRadius: 10, padding: 12, background: "#fff" }}>
            <div style={{ fontWeight: 600, marginBottom: 8 }}>持仓明细</div>
            {analysis.items.length === 0 ? (
              <div style={{ fontSize: 12, color: "#718096" }}>暂无持仓数据</div>
            ) : (
              <div style={{ display: "grid", gap: 8 }}>
                {analysis.items.map((item) => (
                  <div key={item.symbol} style={{ display: "flex", justifyContent: "space-between", fontSize: 13 }}>
                    <span>
                      {item.symbol} {item.sector ? `· ${item.sector}` : ""}
                    </span>
                    <span style={{ fontWeight: 600 }}>
                      {formatNumber(item.latest_price)} · {formatPercent(item.pnl_pct)}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>
      ) : null}
    </div>
  );
}
