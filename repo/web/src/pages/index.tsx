import React, { useState } from "react";

import { Heatmap } from "../components/Heatmap";
import { IndexCards } from "../components/IndexCards";

export default function HomePage() {
  const [asOf, setAsOf] = useState("");
  const [market, setMarket] = useState("");
  const [minChange, setMinChange] = useState("");
  const [maxChange, setMaxChange] = useState("");

  return (
    <div style={{ padding: "24px", display: "flex", flexDirection: "column", gap: 24 }}>
      <section>
        <h2 style={{ fontSize: 20, marginBottom: 12 }}>指数概览</h2>
        <IndexCards asOf={asOf || undefined} />
      </section>
      <section>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <h2 style={{ fontSize: 20 }}>行业热力图</h2>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <input
              type="date"
              value={asOf}
              onChange={(event) => setAsOf(event.target.value)}
              style={{ padding: "4px 8px" }}
            />
            <select value={market} onChange={(event) => setMarket(event.target.value)} style={{ padding: "4px 8px" }}>
              <option value="">全部市场</option>
              <option value="A">A股</option>
              <option value="HK">港股</option>
            </select>
            <input
              type="number"
              placeholder="最小涨跌"
              value={minChange}
              onChange={(event) => setMinChange(event.target.value)}
              style={{ width: 120, padding: "4px 8px" }}
            />
            <input
              type="number"
              placeholder="最大涨跌"
              value={maxChange}
              onChange={(event) => setMaxChange(event.target.value)}
              style={{ width: 120, padding: "4px 8px" }}
            />
          </div>
        </div>
        <Heatmap
          asOf={asOf || undefined}
          market={market || undefined}
          minChange={minChange ? Number(minChange) : undefined}
          maxChange={maxChange ? Number(maxChange) : undefined}
        />
      </section>
      <section style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <a href="/stats" style={{ color: "#2b6cb0", fontWeight: 600 }}>
          前往统计面板 →
        </a>
        <a href="/macro" style={{ color: "#2b6cb0", fontWeight: 600 }}>
          前往宏观指标 →
        </a>
      </section>
    </div>
  );
}
