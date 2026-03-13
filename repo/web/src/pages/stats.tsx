import React, { useState } from "react";

import { PortfolioAnalysisPanel } from "../components/PortfolioAnalysisPanel";
import { StatsDashboard } from "../components/StatsDashboard";

export default function StatsPage() {
  const [symbol, setSymbol] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  return (
    <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: 24 }}>
      <section>
        <h2 style={{ fontSize: 20, marginBottom: 12 }}>统计面板</h2>
        <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 12 }}>
          <input
            type="text"
            value={symbol}
            onChange={(event) => setSymbol(event.target.value.trim().toUpperCase())}
            placeholder="筛选标的（可选）"
            style={{ padding: "6px 10px", border: "1px solid #e2e8f0", borderRadius: 6 }}
          />
          <input
            type="date"
            value={start}
            onChange={(event) => setStart(event.target.value)}
            style={{ padding: "6px 10px", border: "1px solid #e2e8f0", borderRadius: 6 }}
          />
          <input
            type="date"
            value={end}
            onChange={(event) => setEnd(event.target.value)}
            style={{ padding: "6px 10px", border: "1px solid #e2e8f0", borderRadius: 6 }}
          />
        </div>
        <StatsDashboard symbol={symbol || undefined} start={start || undefined} end={end || undefined} />
      </section>
      <section>
        <h2 style={{ fontSize: 20, marginBottom: 12 }}>行业暴露与组合分析</h2>
        <PortfolioAnalysisPanel />
      </section>
    </div>
  );
}
