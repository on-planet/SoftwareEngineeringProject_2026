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
    <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: 24 }}>
      <section>
        <h2 style={{ fontSize: 20, marginBottom: 12 }}>基本面概览</h2>
        <div style={{ display: "flex", gap: 12, marginBottom: 12 }}>
          <input
            type="text"
            value={currentSymbol}
            onChange={handleChange}
            placeholder="输入股票代码"
            style={{ padding: "6px 10px", border: "1px solid #e2e8f0", borderRadius: 6 }}
          />
        </div>
        <StockFundamental symbol={appliedSymbol} />
      </section>
      <section>
        <h2 style={{ fontSize: 20, marginBottom: 12 }}>技术指标</h2>
        <StockIndicatorsChart symbol={appliedSymbol} />
      </section>
      <section>
        <h2 style={{ fontSize: 20, marginBottom: 12 }}>风险指标</h2>
        <StockRiskChart symbol={appliedSymbol} />
      </section>
      <section>
        <h2 style={{ fontSize: 20, marginBottom: 12 }}>相关新闻</h2>
        <NewsList symbol={appliedSymbol} />
      </section>
    </div>
  );
}
