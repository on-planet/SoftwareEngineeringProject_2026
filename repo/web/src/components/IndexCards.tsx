import React, { useEffect, useMemo } from "react";

import { useApiQuery } from "../hooks/useApiQuery";
import { INDEX_NAME_MAP, INDEX_OPTIONS } from "../constants/indices";
import {
  buildIndicesQueryKey,
  getIndices,
  getIndicesQueryOptions,
  primeApiQuery,
} from "../services/api";
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
  { key: "A", label: "A Share", hint: "Shanghai, Shenzhen, STAR, and Beijing benchmarks" },
  { key: "HK", label: "Hong Kong", hint: "HSI, HSCEI, and Hang Seng Tech" },
];

const INDEX_ORDER_MAP = new Map(INDEX_OPTIONS.map((item, index) => [item.symbol, index]));

type Props = {
  asOf?: string;
  activeMarket: IndexMarket;
  selectedSymbol: string;
  onMarketChange: (market: IndexMarket) => void;
  onSymbolChange: (symbol: string) => void;
  initialPage?: IndexPage;
};

export function IndexCards({
  asOf,
  activeMarket,
  selectedSymbol,
  onMarketChange,
  onSymbolChange,
  initialPage,
}: Props) {
  const cacheKey = useMemo(() => buildIndicesQueryKey(asOf), [asOf]);

  useEffect(() => {
    if (!initialPage) {
      return;
    }
    primeApiQuery(cacheKey, initialPage, getIndicesQueryOptions(cacheKey));
  }, [cacheKey, initialPage]);

  const listQuery = useApiQuery<IndexPage>(
    cacheKey,
    () => getIndices({ as_of: asOf }) as Promise<IndexPage>,
    getIndicesQueryOptions(cacheKey),
  );
  const pageData = listQuery.data ?? initialPage ?? null;
  const data = pageData?.items ?? [];
  const loading = listQuery.isLoading && !pageData;
  const error = !pageData ? listQuery.error?.message ?? null : null;

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
    return <div className="helper">Loading index snapshot...</div>;
  }

  if (error) {
    return <div className="helper">{`Failed to load index snapshot: ${error}`}</div>;
  }

  if (data.length === 0) {
    return <div className="helper">No index snapshot data.</div>;
  }

  return (
    <div className="index-snapshot">
      <div className="index-snapshot-head">
        <div>
          <div className="card-title">Market Switch</div>
          <div className="helper">
            {activeMarketMeta.hint}
            {visibleItems.length ? ` | ${visibleItems.length} indices` : ""}
          </div>
        </div>
        <div className="index-market-switch" role="tablist" aria-label="Index market switch">
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

      <div key={activeMarket} className="motion-tab-panel">
        {!visibleItems.length ? (
          <div className="helper">
            No {activeMarket === "A" ? "A Share" : "Hong Kong"} index data.
          </div>
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
                  <div className="card-title">
                    {INDEX_NAME_MAP[item.symbol] || item.name || item.symbol}
                  </div>
                  <div className="index-card-meta">
                    <span>{item.symbol}</span>
                    {item.market ? <span className="index-card-market">{item.market}</span> : null}
                  </div>
                  <div className="helper" style={{ marginTop: 6 }}>
                    {item.date}
                  </div>
                  <div className="index-card-close">{formatNumber(item.close)}</div>
                  <div style={{ marginTop: 4, color: changeColor, fontWeight: 700 }}>
                    {formatSigned(item.change)}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
