import React, { useEffect, useMemo, useState } from "react";

import { getFutures } from "../services/api";
import { formatNumber, formatPercent, formatSigned } from "../utils/format";
import { formatContractMonth, FUTURES_LABELS, sortPreferredFutures } from "../utils/futures";
import { readPersistentCache, writePersistentCache } from "../utils/persistentCache";

type FuturesItem = {
  symbol: string;
  name?: string | null;
  date: string;
  contract_month?: string | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  close?: number | null;
  volume?: number | null;
  source?: string | null;
};

type FuturesPage = {
  items: FuturesItem[];
  total: number;
  limit: number;
  offset: number;
};

const FUTURES_CARDS_CACHE_TTL_MS = 10 * 60 * 1000;

function buildFuturesCardsCacheKey() {
  return "futures-cards:latest";
}

function toLatestBySymbol(items: FuturesItem[]): FuturesItem[] {
  const map = new Map<string, FuturesItem>();
  for (const item of items) {
    if (!item.symbol || !item.date) {
      continue;
    }
    const current = map.get(item.symbol);
    if (!current || new Date(item.date).getTime() > new Date(current.date).getTime()) {
      map.set(item.symbol, item);
    }
  }
  return sortPreferredFutures(Array.from(map.values()));
}

export function FuturesCards() {
  const [items, setItems] = useState<FuturesItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const cacheKey = buildFuturesCardsCacheKey();
    const cachedItems = readPersistentCache<FuturesItem[]>(cacheKey, FUTURES_CARDS_CACHE_TTL_MS);
    if (cachedItems?.length) {
      setItems(cachedItems);
      setLoading(false);
    } else {
      setLoading(true);
    }
    getFutures({ sort: "desc", limit: 240 })
      .then((res) => {
        if (!active) {
          return;
        }
        const page = res as FuturesPage;
        const latest = toLatestBySymbol(page.items ?? []);
        setItems(latest);
        writePersistentCache(cacheKey, latest);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setError(err.message || "Failed to load futures data");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const rows = useMemo(() => items.slice(0, 8), [items]);

  if (loading) {
    return <div className="helper">期货数据加载中...</div>;
  }

  if (error) {
    return <div className="helper">期货数据加载失败: {error}</div>;
  }

  if (rows.length === 0) {
    return <div className="helper">暂无期货数据</div>;
  }

  return (
    <div className="grid grid-3">
      {rows.map((item) => {
        const open = Number(item.open ?? 0);
        const close = Number(item.close ?? 0);
        const delta = close - open;
        const pct = open !== 0 ? delta / open : 0;
        const trendColor = delta >= 0 ? "#f87171" : "#34d399";
        const label = FUTURES_LABELS[item.symbol] || item.name || item.symbol;

        return (
          <div key={`${item.symbol}-${item.date}`} className="card">
            <div className="card-title">{label}</div>
            <div className="helper">
              {item.symbol} | {item.date}
            </div>
            <div className="helper">主力合约: {formatContractMonth(item.contract_month)}</div>
            <div style={{ marginTop: 8, fontSize: 20, fontWeight: 700 }}>
              {formatNumber(close)}
            </div>
            <div style={{ marginTop: 4, color: trendColor, fontWeight: 600 }}>
              {formatSigned(delta)} ({delta === 0 ? "0.00%" : formatPercent(pct)})
            </div>
            <div className="helper" style={{ marginTop: 6 }}>
              H {formatNumber(Number(item.high ?? 0))} | L {formatNumber(Number(item.low ?? 0))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
