import React, { useEffect, useMemo, useState } from "react";

import { INDEX_NAME_MAP, INDEX_OPTIONS } from "../constants/indices";
import { getIndices } from "../services/api";
import { formatNumber, formatSigned } from "../utils/format";

type IndexMarket = "A" | "HK";

type IndexItem = {
  symbol: string;
  name?: string | null;
  market?: string | null;
  date: string;
  close: number;
  change: number;
};

type IndexPage = {
  items: IndexItem[];
  total: number;
  limit: number;
  offset: number;
};

const MARKET_OPTIONS: Array<{ key: IndexMarket; label: string; hint: string }> = [
  { key: "A", label: "A 股", hint: "上证、深证、科创与北交所宽基" },
  { key: "HK", label: "港股", hint: "恒生、国企与恒生科技" },
];

const INDEX_ORDER_MAP = new Map(INDEX_OPTIONS.map((item, index) => [item.symbol, index]));

type Props = {
  asOf?: string;
  activeMarket: IndexMarket;
  selectedSymbol: string;
  onMarketChange: (market: IndexMarket) => void;
  onSymbolChange: (symbol: string) => void;
};

export function IndexCards({ asOf, activeMarket, selectedSymbol, onMarketChange, onSymbolChange }: Props) {
  const [data, setData] = useState<IndexItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getIndices({ as_of: asOf })
      .then((res) => {
        if (!active) {
          return;
        }
        const page = res as IndexPage;
        setData(page.items ?? []);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setError(err.message || "指数数据加载失败");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [asOf]);

  const visibleItems = useMemo(() => {
    const marketItems = data.filter((item) => (item.market || "").toUpperCase() === activeMarket);
    const bySymbol = new Map(marketItems.map((item) => [item.symbol, item]));
    const preferredItems = INDEX_OPTIONS.filter((item) => item.market === activeMarket)
      .map((item) => bySymbol.get(item.symbol))
      .filter((item): item is IndexItem => Boolean(item));
    const remainingItems = marketItems
      .filter((item) => !INDEX_ORDER_MAP.has(item.symbol))
      .sort((left, right) => left.symbol.localeCompare(right.symbol));
    return [...preferredItems, ...remainingItems];
  }, [activeMarket, data]);

  const activeMarketMeta = MARKET_OPTIONS.find((item) => item.key === activeMarket) || MARKET_OPTIONS[0];

  if (loading) {
    return <div className="helper">指数数据加载中...</div>;
  }

  if (error) {
    return <div className="helper">指数数据加载失败：{error}</div>;
  }

  if (data.length === 0) {
    return <div className="helper">暂无指数数据。</div>;
  }

  return (
    <div className="index-snapshot">
      <div className="index-snapshot-head">
        <div>
          <div className="card-title">市场切换</div>
          <div className="helper">
            {activeMarketMeta.hint}
            {visibleItems.length ? ` · 共 ${visibleItems.length} 个指数` : ""}
          </div>
        </div>
        <div className="index-market-switch" role="tablist" aria-label="指数市场切换">
          {MARKET_OPTIONS.map((item) => (
            <button
              key={item.key}
              type="button"
              role="tab"
              aria-selected={item.key === activeMarket}
              className="index-market-button"
              data-active={item.key === activeMarket}
              onClick={() => onMarketChange(item.key)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {!visibleItems.length ? (
        <div className="helper">暂无{activeMarket === "A" ? "A 股" : "港股"}指数数据。</div>
      ) : (
        <div className="grid grid-3">
          {visibleItems.map((item) => {
            const changeColor = item.change >= 0 ? "#ef4444" : "#10b981";
            const isActive = item.symbol === selectedSymbol;
            return (
              <button
                key={`${item.symbol}-${item.date}`}
                type="button"
                className="card index-card index-card-button"
                data-active={isActive}
                onClick={() => onSymbolChange(item.symbol)}
              >
                <div className="card-title">{INDEX_NAME_MAP[item.symbol] || item.name || item.symbol}</div>
                <div className="index-card-meta">
                  <span>{item.symbol}</span>
                  {item.market ? <span className="index-card-market">{item.market}</span> : null}
                </div>
                <div className="helper" style={{ marginTop: 6 }}>
                  {item.date}
                </div>
                <div className="index-card-close">{formatNumber(item.close)}</div>
                <div style={{ marginTop: 4, color: changeColor, fontWeight: 700 }}>{formatSigned(item.change)}</div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
