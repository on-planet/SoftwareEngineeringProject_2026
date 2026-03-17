import React, { useMemo, useState } from "react";
import { useRouter } from "next/router";

import { FuturesCards } from "../components/FuturesCards";
import { Heatmap } from "../components/Heatmap";
import { IndexCards } from "../components/IndexCards";
import { IndexKlinePanel } from "../components/IndexKlinePanel";
import { INDEX_OPTIONS, inferIndexMarket } from "../constants/indices";

const heroCards = [
  { label: "市场覆盖", value: "A股 + 港股", hint: "默认覆盖实时股票池，支持直接进入个股详情页" },
  { label: "数据链路", value: "多源行情", hint: "统一接入指数、个股、期货、财报、研报与事件序列" },
  { label: "K线周期", value: "分钟到年线", hint: "支持 1m、30m、60m、日、周、月、季、年等周期" },
];

const actionCards = [
  {
    title: "股票中心",
    description: "查看 A 股和港股股票池，进入每只股票的独立详情页。",
    href: "/stocks",
    tone: "blue",
  },
  {
    title: "市场洞察",
    description: "查看新闻、事件、成分股、热力图和行业暴露等视图。",
    href: "/insights",
    tone: "slate",
  },
  {
    title: "宏观看板",
    description: "查看宏观指标快照以及时间序列变化。",
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
  const [selectedIndexSymbol, setSelectedIndexSymbol] = useState<string>(INDEX_OPTIONS[0]?.symbol ?? "000001.SH");
  const [heatmapMarket, setHeatmapMarket] = useState<"A" | "HK">("A");
  const selectedIndex = useMemo(
    () => INDEX_OPTIONS.find((item) => item.symbol === selectedIndexSymbol) ?? null,
    [selectedIndexSymbol],
  );
  const activeIndexMarket = selectedIndex?.market ?? inferIndexMarket(selectedIndexSymbol);

  const handleIndexSymbolChange = (symbol: string) => {
    setSelectedIndexSymbol(symbol);
  };

  const handleIndexMarketChange = (market: "A" | "HK") => {
    const nextSymbol = INDEX_OPTIONS.find((item) => item.market === market)?.symbol;
    if (nextSymbol) {
      setSelectedIndexSymbol(nextSymbol);
    }
  };

  return (
    <div className="page">
      <section className="card hero-card">
        <div className="page-header">
          <div>
            <h1 className="page-title">KiloQuant 市场总览</h1>
            <p className="helper">聚合指数、个股、期货、行业热力图与多周期 K 线的实时看板。</p>
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
          <IndexCards
            activeMarket={activeIndexMarket}
            selectedSymbol={selectedIndexSymbol}
            onMarketChange={handleIndexMarketChange}
            onSymbolChange={handleIndexSymbolChange}
          />
        </div>
      </section>

      <section>
        <h2 className="section-title">指数 K 线</h2>
        <IndexKlinePanel
          symbol={selectedIndexSymbol}
          activeMarket={activeIndexMarket}
          onMarketChange={handleIndexMarketChange}
          onSymbolChange={handleIndexSymbolChange}
        />
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
          <div className="toolbar" style={{ marginBottom: 12 }}>
            <button
              type="button"
              className="chip-button"
              data-active={heatmapMarket === "A"}
              onClick={() => setHeatmapMarket("A")}
            >
              A股
            </button>
            <button
              type="button"
              className="chip-button"
              data-active={heatmapMarket === "HK"}
              onClick={() => setHeatmapMarket("HK")}
            >
              港股
            </button>
          </div>
          <Heatmap market={heatmapMarket} showMarketSelector={false} />
        </div>
      </section>
    </div>
  );
}
