import React, { useEffect, useMemo, useState } from "react";

import { getFutures } from "../services/api";
import { formatNumber, formatPercent, formatSigned } from "../utils/format";
import {
  formatContractMonth,
  FUTURES_CATEGORIES,
  FUTURES_LABELS,
  getFuturesCategory,
  sortPreferredFutures,
} from "../utils/futures";
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

type FuturesCardsProps = {
  initialItems?: FuturesItem[];
};

const FUTURES_CARDS_CACHE_TTL_MS = 10 * 60 * 1000;
const OVERVIEW_ITEMS_PER_CATEGORY = 3;

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

function FuturesSnapshotCard({ item }: { item: FuturesItem }) {
  const open = Number(item.open ?? 0);
  const close = Number(item.close ?? 0);
  const delta = close - open;
  const pct = open !== 0 ? delta / open : 0;
  const trendColor = delta >= 0 ? "#f87171" : "#34d399";
  const label = FUTURES_LABELS[item.symbol] || item.name || item.symbol;

  return (
    <div className="card">
      <div className="card-title">{label}</div>
      <div className="helper">
        {item.symbol} | {item.date}
      </div>
      <div className="helper">主力合约: {formatContractMonth(item.contract_month)}</div>
      <div style={{ marginTop: 8, fontSize: 20, fontWeight: 700 }}>{formatNumber(close)}</div>
      <div style={{ marginTop: 4, color: trendColor, fontWeight: 600 }}>
        {formatSigned(delta)} ({delta === 0 ? "0.00%" : formatPercent(pct)})
      </div>
      <div className="helper" style={{ marginTop: 6 }}>
        H {formatNumber(Number(item.high ?? 0))} | L {formatNumber(Number(item.low ?? 0))}
      </div>
    </div>
  );
}

export function FuturesCards({ initialItems }: FuturesCardsProps) {
  const [items, setItems] = useState<FuturesItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const cacheKey = buildFuturesCardsCacheKey();
    if (initialItems !== undefined) {
      const latest = toLatestBySymbol(initialItems);
      setItems(latest);
      setLoading(false);
      setError(null);
      writePersistentCache(cacheKey, latest);
      return () => {
        active = false;
      };
    }
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
        setError(err.message || "期货数据加载失败");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [initialItems]);

  const categoryGroups = useMemo(() => {
    const grouped = new Map<string, FuturesItem[]>();
    for (const item of items) {
      const category = getFuturesCategory(item.symbol);
      grouped.set(category, [...(grouped.get(category) ?? []), item]);
    }
    const knownGroups = FUTURES_CATEGORIES.filter((category) => category !== FUTURES_CATEGORIES[0])
      .map((category) => ({ category, rows: grouped.get(category) ?? [] }))
      .filter((group) => group.rows.length > 0);
    const known = new Set(FUTURES_CATEGORIES as readonly string[]);
    const extraGroups = Array.from(grouped.entries())
      .filter(([category]) => !known.has(category))
      .map(([category, rows]) => ({ category, rows }));
    return [...knownGroups, ...extraGroups];
  }, [items]);

  if (loading) {
    return (
      <div className="grid grid-3">
        {Array.from({ length: 3 }, (_, i) => (
          <div key={i} className="skeleton-card" />
        ))}
      </div>
    );
  }

  if (error) {
    return <div className="helper">期货数据加载失败: {error}</div>;
  }

  if (categoryGroups.length === 0) {
    return <div className="helper">暂无期货数据</div>;
  }

  return (
    <div style={{ display: "grid", gap: 18 }}>
      {categoryGroups.map((group) => (
        <div key={group.category}>
          <div className="panel-header" style={{ marginBottom: 10 }}>
            <div className="card-title">{group.category}</div>
            <div className="helper">{group.rows.length} 个品种</div>
          </div>
          <div className="grid grid-3">
            {group.rows.slice(0, OVERVIEW_ITEMS_PER_CATEGORY).map((item) => (
              <FuturesSnapshotCard key={`${item.symbol}-${item.date}`} item={item} />
            ))}
          </div>
          {group.rows.length > OVERVIEW_ITEMS_PER_CATEGORY ? (
            <div className="helper" style={{ marginTop: 8 }}>
              还有 {group.rows.length - OVERVIEW_ITEMS_PER_CATEGORY} 个品种，可在期货页查看全部。
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
