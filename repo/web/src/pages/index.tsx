import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";

import { FuturesCards } from "../components/FuturesCards";
import { Heatmap } from "../components/Heatmap";
import { IndexCards } from "../components/IndexCards";
import { IndexKlinePanel } from "../components/IndexKlinePanel";
import { INDEX_OPTIONS, inferIndexMarket } from "../constants/indices";
import {
  buildIndicesQueryKey,
  DashboardOverviewResponse,
  getDashboardOverview,
  getIndicesQueryOptions,
  primeApiQuery,
} from "../services/api";

function buildMotionStyle(index: number): React.CSSProperties {
  return { ["--motion-index" as "--motion-index"]: index } as React.CSSProperties;
}

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
  const [overview, setOverview] = useState<DashboardOverviewResponse | null | undefined>(undefined);
  const selectedIndex = useMemo(
    () => INDEX_OPTIONS.find((item) => item.symbol === selectedIndexSymbol) ?? null,
    [selectedIndexSymbol],
  );
  const activeIndexMarket = selectedIndex?.market ?? inferIndexMarket(selectedIndexSymbol);

  useEffect(() => {
    let active = true;
    getDashboardOverview()
      .then((payload) => {
        if (active) {
          const indexCacheKey = buildIndicesQueryKey();
          primeApiQuery(indexCacheKey, payload.indices, getIndicesQueryOptions(indexCacheKey));
          setOverview(payload);
        }
      })
      .catch(() => {
        if (active) {
          setOverview(null);
        }
      });
    return () => {
      active = false;
    };
  }, []);

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
            <h1 className="page-title">QuantPulse 市场总览</h1>
            <p className="helper">聚合指数、个股、期货、行业热力图与多周期 K 线的实时看板。</p>
          </div>
        </div>
        <div className="hero-grid motion-stagger-group">
          {heroCards.map((card, index) => (
            <div key={card.label} className="hero-metric" style={buildMotionStyle(index)}>
              <div className="card-title">{card.label}</div>
              <div className="hero-metric-value">{card.value}</div>
              <div className="helper">{card.hint}</div>
            </div>
          ))}
        </div>
        <div className="action-card-grid motion-stagger-group">
          {actionCards.map((card, index) => (
            <button
              key={card.href}
              type="button"
              className={`action-card action-card-${card.tone}`}
              style={buildMotionStyle(index + heroCards.length)}
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
          {overview === undefined ? (
            <div className="helper">市场总览加载中...</div>
          ) : (
            <IndexCards
              activeMarket={activeIndexMarket}
              selectedSymbol={selectedIndexSymbol}
              onMarketChange={handleIndexMarketChange}
              onSymbolChange={handleIndexSymbolChange}
              initialPage={overview?.indices}
            />
          )}
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
          {overview === undefined ? (
            <div className="helper">市场总览加载中...</div>
          ) : (
            <FuturesCards initialItems={overview?.futures.items} />
          )}
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
          {overview === undefined ? (
            <div className="helper">市场总览加载中...</div>
          ) : (
            <Heatmap
              market={heatmapMarket}
              showMarketSelector={false}
              preloadedPages={
                overview
                  ? {
                      A: overview.heatmap.a,
                      HK: overview.heatmap.hk,
                    }
                  : undefined
              }
            />
          )}
        </div>
      </section>
    </div>
  );
}
