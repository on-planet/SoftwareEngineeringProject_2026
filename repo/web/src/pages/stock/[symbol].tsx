import dynamic from "next/dynamic";
import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";

import { StockFundamental } from "../../components/StockFundamental";

const StockKlinePanel = dynamic(
  () => import("../../components/StockKlinePanel").then((mod) => mod.StockKlinePanel),
  { ssr: false, loading: () => <div className="card helper">K 线加载中...</div> }
);
const StockIndicatorsChart = dynamic(
  () => import("../../components/StockIndicatorsChart").then((mod) => mod.StockIndicatorsChart),
  { ssr: false, loading: () => <div className="helper">技术指标加载中...</div> }
);
const StockRiskChart = dynamic(
  () => import("../../components/StockRiskChart").then((mod) => mod.StockRiskChart),
  { ssr: false, loading: () => <div className="helper">风险分析加载中...</div> }
);
const StockFinancialTable = dynamic(
  () => import("../../components/StockFinancialTable").then((mod) => mod.StockFinancialTable),
  { ssr: false, loading: () => <div className="helper">财务报表加载中...</div> }
);
const StockResearchPanel = dynamic(
  () => import("../../components/StockResearchPanel").then((mod) => mod.StockResearchPanel),
  { ssr: false, loading: () => <div className="helper">研报与业绩预告加载中...</div> }
);

type Props = {
  symbol?: string;
};

export default function StockPage({ symbol = "000001.SZ" }: Props) {
  const router = useRouter();
  const routeSymbol = typeof router.query.symbol === "string" ? router.query.symbol : symbol;
  const normalizedRouteSymbol = useMemo(() => routeSymbol.trim().toUpperCase(), [routeSymbol]);
  const [currentSymbol, setCurrentSymbol] = useState(normalizedRouteSymbol);
  const [showSecondaryPanels, setShowSecondaryPanels] = useState(false);

  useEffect(() => {
    setCurrentSymbol(normalizedRouteSymbol);
  }, [normalizedRouteSymbol]);

  useEffect(() => {
    setShowSecondaryPanels(false);
    const timer = window.setTimeout(() => setShowSecondaryPanels(true), 180);
    return () => window.clearTimeout(timer);
  }, [normalizedRouteSymbol]);

  const appliedSymbol = currentSymbol.trim().toUpperCase() || normalizedRouteSymbol;

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextSymbol = currentSymbol.trim().toUpperCase();
    if (!nextSymbol) {
      return;
    }
    void router.push(`/stock/${encodeURIComponent(nextSymbol)}`);
  };

  return (
    <div className="page">
      <section className="card">
        <div className="page-header">
          <div>
            <h1 className="page-title">个股详情</h1>
            <p className="helper">页面全部直连雪球接口，展示实时快照、盘口、多周期 K 线、财报、技术指标、风险和研报信息。</p>
          </div>
          <form className="toolbar" onSubmit={handleSubmit}>
            <input
              className="input"
              type="text"
              value={currentSymbol}
              onChange={(event) => setCurrentSymbol(event.target.value)}
              placeholder="输入股票代码，例如 600000、000001.SZ、00700.HK"
            />
            <button type="submit" className="primary-button">
              打开详情
            </button>
          </form>
        </div>
      </section>

      <section>
        <StockFundamental symbol={appliedSymbol} />
      </section>

      <section>
        <StockKlinePanel symbol={appliedSymbol} />
      </section>

      <section className="split-grid">
        <div>
          <h2 className="section-title">技术指标</h2>
          <div className="card">
            {showSecondaryPanels ? <StockIndicatorsChart symbol={appliedSymbol} /> : <div className="helper">技术指标准备中...</div>}
          </div>
        </div>
        <div>
          <h2 className="section-title">风险分析</h2>
          <div className="card">
            {showSecondaryPanels ? <StockRiskChart symbol={appliedSymbol} /> : <div className="helper">风险分析准备中...</div>}
          </div>
        </div>
      </section>

      <section>
        <h2 className="section-title">财务报表</h2>
        <div className="card">
          {showSecondaryPanels ? <StockFinancialTable symbol={appliedSymbol} /> : <div className="helper">财务报表准备中...</div>}
        </div>
      </section>

      <section>
        <h2 className="section-title">研报与业绩预告</h2>
        <div className="card">
          {showSecondaryPanels ? <StockResearchPanel symbol={appliedSymbol} /> : <div className="helper">研报与业绩预告准备中...</div>}
        </div>
      </section>
    </div>
  );
}
