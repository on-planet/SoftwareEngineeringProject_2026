import React from "react";
import { useRouter } from "next/router";

import { FuturesCards } from "../components/FuturesCards";
import { Heatmap } from "../components/Heatmap";
import { IndexCards } from "../components/IndexCards";
import { IndexKlinePanel } from "../components/IndexKlinePanel";

const heroCards = [
  { label: "Markets", value: "A + HK", hint: "200 default stock pages ready for bootstrap" },
  { label: "Signals", value: "Daily", hint: "Indices, futures, heatmap, risk, and indicators" },
  { label: "Views", value: "Kline", hint: "Day, week, month, quarter, and year aggregation" },
];

const actionCards = [
  {
    title: "Stocks",
    description: "Browse 100 A-share and 100 Hong Kong stocks. Every symbol has its own detail page.",
    href: "/stocks",
    tone: "blue",
  },
  {
    title: "Insights",
    description: "Open news, events, constituents, and sector exposure views.",
    href: "/insights",
    tone: "slate",
  },
  {
    title: "Macro",
    description: "Review macro factors and the latest time series snapshots.",
    href: "/macro",
    tone: "amber",
  },
  {
    title: "Futures",
    description: "Track major futures contracts such as gold, crude oil, natural gas, and copper.",
    href: "/futures",
    tone: "blue",
  },
];

export default function HomePage() {
  const router = useRouter();

  return (
    <div className="page">
      <section className="card hero-card">
        <div className="page-header">
          <div>
            <h1 className="page-title">KiloQuant Dashboard</h1>
            <p className="helper">
              Unified view for indices, stocks, futures, sector exposure, and the multi-period kline data
              pipeline.
            </p>
          </div>
        </div>
        <div className="hero-grid">
          {heroCards.map((card) => (
            <div key={card.label} className="hero-metric">
              <div className="card-title">{card.label}</div>
              <div className="hero-metric-value">{card.value}</div>
              <div className="helper">{card.hint}</div>
            </div>
          ))}
        </div>
        <div className="action-card-grid">
          {actionCards.map((card) => (
            <button
              key={card.href}
              type="button"
              className={`action-card action-card-${card.tone}`}
              onClick={() => {
                void router.push(card.href);
              }}
            >
              <div className="action-card-label">{card.title}</div>
              <div className="action-card-desc">{card.description}</div>
              <div className="action-card-arrow">Open {">"}</div>
            </button>
          ))}
        </div>
      </section>

      <section>
        <h2 className="section-title">Index Snapshot</h2>
        <div className="card">
          <IndexCards />
        </div>
      </section>

      <section>
        <h2 className="section-title">Index Kline</h2>
        <IndexKlinePanel />
      </section>

      <section>
        <h2 className="section-title">Futures Snapshot</h2>
        <div className="card">
          <FuturesCards />
        </div>
      </section>

      <section>
        <h2 className="section-title">Sector Heatmap</h2>
        <div className="card">
          <Heatmap />
        </div>
      </section>
    </div>
  );
}
