import React, { useState } from "react";

import { PortfolioAnalysisPanel } from "../components/PortfolioAnalysisPanel";
import { StatsDashboard } from "../components/StatsDashboard";

export default function StatsPage() {
  const [symbol, setSymbol] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  return (
    <div className="page">
      <section>
        <h2 className="section-title">统计面板</h2>
        <div className="toolbar" style={{ marginBottom: 12 }}>
          <input
            className="input"
            type="text"
            value={symbol}
            onChange={(event) => setSymbol(event.target.value.trim().toUpperCase())}
            placeholder="筛选标的（可选）"
          />
          <input className="input" type="date" value={start} onChange={(event) => setStart(event.target.value)} />
          <input className="input" type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
        </div>
        <StatsDashboard symbol={symbol || undefined} start={start || undefined} end={end || undefined} />
      </section>
      <section>
        <h2 className="section-title">行业暴露与组合分析</h2>
        <div className="card">
          <PortfolioAnalysisPanel />
        </div>
      </section>
    </div>
  );
}
