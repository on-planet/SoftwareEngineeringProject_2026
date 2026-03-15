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
            <h1 className="page-title">Stock Detail</h1>
            <p className="helper">
              Interface-only page with profile, multi-period kline, live financials, research reports, earning
              forecasts, indicators, and risk.
            </p>
          </div>
          <form className="toolbar" onSubmit={handleSubmit}>
            <input
              className="input"
              type="text"
              value={currentSymbol}
              onChange={(event) => setCurrentSymbol(event.target.value)}
              placeholder="Enter symbol, for example 600000 or 00700.HK"
            />
            <button type="submit" className="primary-button">
              Open
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
          <h2 className="section-title">Technical Indicators</h2>
          <div className="card">
            <StockIndicatorsChart symbol={appliedSymbol} />
          </div>
        </div>
        <div>
          <h2 className="section-title">Risk Snapshot</h2>
          <div className="card">
            <StockRiskChart symbol={appliedSymbol} />
          </div>
        </div>
      </section>

      <section>
        <h2 className="section-title">Financial Statements</h2>
        <div className="card">
          <StockFinancialTable symbol={appliedSymbol} />
        </div>
      </section>

      <section>
        <h2 className="section-title">Research And Forecasts</h2>
        <div className="card">
          <StockResearchPanel symbol={appliedSymbol} />
        </div>
      </section>
    </div>
  );
}
