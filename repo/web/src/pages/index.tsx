import React from "react";
import { useRouter } from "next/router";

import { FuturesCards } from "../components/FuturesCards";
import { Heatmap } from "../components/Heatmap";
import { IndexCards } from "../components/IndexCards";
import { IndexKlinePanel } from "../components/IndexKlinePanel";

const heroCards = [
  { label: "市场覆盖", value: "A 股 + 港股", hint: "默认实时股票池各 100 只，可直接进入独立详情页" },
  { label: "数据链路", value: "雪球接口", hint: "指数、个股、期货、财报、研报和业绩预告统一直连" },
  { label: "K 线周期", value: "1 分钟到年线", hint: "支持 1m、30m、60m、日、周、月、季、年" },
];

const actionCards = [
  {
    title: "股票中心",
    description: "查看 A 股和港股实时股票池，进入每只股票的独立详情页。",
    href: "/stocks",
    tone: "blue",
  },
  {
    title: "市场洞察",
    description: "查看新闻、事件、成分股和行业暴露等视图。",
    href: "/insights",
    tone: "slate",
  },
  {
    title: "宏观看板",
    description: "查看宏观指标快照及时间序列变化。",
    href: "/macro",
    tone: "amber",
  },
  {
    title: "期货跟踪",
    description: "跟踪黄金、原油、天然气、铜等主要期货合约。",
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
            <h1 className="page-title">KiloQuant 市场总览</h1>
            <p className="helper">聚合指数、个股、期货、行业热力图与多周期 K 线的实时接口看板。</p>
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
              <div className="action-card-arrow">进入 {">"}</div>
            </button>
          ))}
        </div>
      </section>

      <section>
        <h2 className="section-title">指数快照</h2>
        <div className="card">
          <IndexCards />
        </div>
      </section>

      <section>
        <h2 className="section-title">指数 K 线</h2>
        <IndexKlinePanel />
      </section>

      <section>
        <h2 className="section-title">期货快照</h2>
        <div className="card">
          <FuturesCards />
        </div>
      </section>

      <section>
        <h2 className="section-title">行业热力图</h2>
        <div className="card">
          <Heatmap />
        </div>
      </section>
    </div>
  );
}
