import React, { useState } from "react";

import { NewsList } from "../../components/NewsList";
import { StockFundamental } from "../../components/StockFundamental";
import { StockIndicatorsChart } from "../../components/StockIndicatorsChart";
import { StockRiskChart } from "../../components/StockRiskChart";

type Props = {
  symbol?: string;
};

export default function StockPage({ symbol = "000001" }: Props) {
  const [currentSymbol, setCurrentSymbol] = useState(symbol);

  const handleChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setCurrentSymbol(event.target.value.trim().toUpperCase());
  };

  const appliedSymbol = currentSymbol || symbol;
  return (
    <div className="page">
      <section>
        <h2 className="section-title">基本面概览</h2>
        <div className="toolbar" style={{ marginBottom: 12 }}>
          <input
            className="input"
            type="text"
            value={currentSymbol}
            onChange={handleChange}
            placeholder="输入股票代码"
          />
        </div>
        <div className="card">
          <StockFundamental symbol={appliedSymbol} />
        </div>
      </section>
      <section>
        <h2 className="section-title">技术指标</h2>
        <div className="card">
          <StockIndicatorsChart symbol={appliedSymbol} />
        </div>
      </section>
      <section>
        <h2 className="section-title">风险指标</h2>
        <div className="card">
          <StockRiskChart symbol={appliedSymbol} />
        </div>
      </section>
      <section>
        <h2 className="section-title">相关新闻</h2>
        <div className="card">
          <NewsList symbol={appliedSymbol} />
        </div>
      </section>
    </div>
  );
}
