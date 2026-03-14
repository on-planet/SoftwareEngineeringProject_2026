import React, { useMemo } from "react";
import { useRouter } from "next/router";

import { Heatmap } from "../components/Heatmap";
import { IndexCards } from "../components/IndexCards";

const heroCards = [
  { label: "宏观指标", value: "实时更新", hint: "多维宏观因子" },
  { label: "新闻洞察", value: "聚合快讯", hint: "多源 RSS" },
  { label: "事件追踪", value: "时间线", hint: "公告与异动" },
];

const actionCards = [
  { title: "进入数据洞察", description: "查看新闻聚合、事件时间线、指数成分与行业暴露。", href: "/insights", tone: "blue" },
  { title: "进入宏观指标", description: "按国家和指标查看宏观序列与最新快照。", href: "/macro", tone: "amber" },
  { title: "进入统计面板", description: "浏览事件与新闻的聚合统计结果。", href: "/stats", tone: "slate" },
];

export default function HomePage() {
  const router = useRouter();
  const heroStyle = useMemo(
    () => ({
      display: "grid",
      gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
      gap: 16,
      marginBottom: 16,
    }),
    []
  );

  return (
    <div className="page">
      <section>
        <div className="card" style={{ background: "linear-gradient(135deg, #ffffff 0%, #eef2ff 100%)" }}>
          <h1 style={{ fontSize: 28, margin: 0 }}>KiloQuant 市场洞察</h1>
          <p className="helper" style={{ marginTop: 8, fontSize: 14 }}>
            汇聚指数、行业热力图、宏观与新闻事件的每日概览。
          </p>
          <div style={heroStyle}>
            {heroCards.map((card) => (
              <div key={card.label} className="card" style={{ boxShadow: "none" }}>
                <div className="card-title">{card.label}</div>
                <div style={{ fontSize: 20, fontWeight: 700 }}>{card.value}</div>
                <div className="helper" style={{ marginTop: 6 }}>{card.hint}</div>
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
                <div className="action-card-arrow">立即查看 →</div>
              </button>
            ))}
          </div>
        </div>
      </section>
      <section>
        <h2 className="section-title">指数概览</h2>
        <div className="card">
          <IndexCards />
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
