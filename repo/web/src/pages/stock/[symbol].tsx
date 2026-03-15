import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";

import { StockFinancialTable } from "../../components/StockFinancialTable";
import { StockFundamental } from "../../components/StockFundamental";
import { StockIndicatorsChart } from "../../components/StockIndicatorsChart";
import { StockKlinePanel } from "../../components/StockKlinePanel";
import { StockResearchPanel } from "../../components/StockResearchPanel";
import { StockRiskChart } from "../../components/StockRiskChart";

type Props = {
  symbol?: string;
};

export default function StockPage({ symbol = "000001.SZ" }: Props) {
  const router = useRouter();
  const routeSymbol = typeof router.query.symbol === "string" ? router.query.symbol : symbol;
  const normalizedRouteSymbol = useMemo(() => routeSymbol.trim().toUpperCase(), [routeSymbol]);
  const [currentSymbol, setCurrentSymbol] = useState(normalizedRouteSymbol);

  useEffect(() => {
    setCurrentSymbol(normalizedRouteSymbol);
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
            <StockIndicatorsChart symbol={appliedSymbol} />
          </div>
        </div>
        <div>
          <h2 className="section-title">风险分析</h2>
          <div className="card">
            <StockRiskChart symbol={appliedSymbol} />
          </div>
        </div>
      </section>

      <section>
        <h2 className="section-title">财务报表</h2>
        <div className="card">
          <StockFinancialTable symbol={appliedSymbol} />
        </div>
      </section>

      <section>
        <h2 className="section-title">研报与业绩预告</h2>
        <div className="card">
          <StockResearchPanel symbol={appliedSymbol} />
        </div>
      </section>
    </div>
  );
}
