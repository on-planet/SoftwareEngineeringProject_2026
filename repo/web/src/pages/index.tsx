import React, { useState } from "react";

import { Heatmap } from "../components/Heatmap";
import { IndexCards } from "../components/IndexCards";

export default function HomePage() {
  const [asOf, setAsOf] = useState("");
  const [market, setMarket] = useState("");
  const [minChange, setMinChange] = useState("");
  const [maxChange, setMaxChange] = useState("");

  return (
    <div className="page">
      <section>
        <h2 className="section-title">指数概览</h2>
        <div className="card">
          <IndexCards asOf={asOf || undefined} />
        </div>
      </section>
      <section>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12, flexWrap: "wrap", gap: 12 }}>
          <h2 className="section-title">行业热力图</h2>
          <div className="toolbar">
            <input
              className="input"
              type="date"
              value={asOf}
              onChange={(event) => setAsOf(event.target.value)}
            />
            <select className="select" value={market} onChange={(event) => setMarket(event.target.value)}>
              <option value="">全部市场</option>
              <option value="A">A股</option>
              <option value="HK">港股</option>
            </select>
            <input
              className="input"
              type="number"
              placeholder="最小涨跌"
              value={minChange}
              onChange={(event) => setMinChange(event.target.value)}
              style={{ width: 120 }}
            />
            <input
              className="input"
              type="number"
              placeholder="最大涨跌"
              value={maxChange}
              onChange={(event) => setMaxChange(event.target.value)}
              style={{ width: 120 }}
            />
          </div>
        </div>
        <div className="card">
          <Heatmap
            asOf={asOf || undefined}
            market={market || undefined}
            minChange={minChange ? Number(minChange) : undefined}
            maxChange={maxChange ? Number(maxChange) : undefined}
          />
        </div>
      </section>
      <section style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <a href="/stats" className="badge-link">
          前往统计面板 →
        </a>
        <a href="/macro" className="badge-link">
          前往宏观指标 →
        </a>
      </section>
    </div>
  );
}
