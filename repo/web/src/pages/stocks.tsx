import Link from "next/link";
import React, { useEffect, useState } from "react";

import { getStocks } from "../services/api";

type StockItem = {
  symbol: string;
  name: string;
  market: string;
  sector: string;
};

type StockPage = {
  items: StockItem[];
  total: number;
  limit: number;
  offset: number;
};

function MarketSection({ market, keyword }: { market: "A" | "HK"; keyword: string }) {
  const [items, setItems] = useState<StockItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getStocks({ market, keyword: keyword || undefined, sort: "asc", limit: 100, offset: 0 })
      .then((res) => {
        if (!active) {
          return;
        }
        const payload = res as StockPage;
        setItems(payload.items ?? []);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setItems([]);
        setError(err.message || "Failed to load stocks");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [keyword, market]);

  return (
    <section>
      <div className="section-headline">
        <h2 className="section-title">{market === "A" ? "A-share Live Pool" : "Hong Kong Live Pool"}</h2>
        <div className="helper">{items.length} symbols loaded</div>
      </div>
      {loading ? <div className="helper">Loading stock list...</div> : null}
      {!loading && error ? <div className="helper">Stock list failed: {error}</div> : null}
      {!loading && !error ? (
        <div className="stock-grid">
          {items.map((item) => (
            <Link key={item.symbol} href={`/stock/${encodeURIComponent(item.symbol)}`} className="stock-card">
              <div className="stock-card-title">{item.name || item.symbol}</div>
              <div className="helper">{item.symbol}</div>
              <div className="stock-card-meta">
                <span>{item.market}</span>
                <span>{item.sector || "Unknown"}</span>
              </div>
            </Link>
          ))}
        </div>
      ) : null}
    </section>
  );
}

export default function StocksPage() {
  const [keyword, setKeyword] = useState("");

  return (
    <div className="page">
      <section className="card">
        <div className="page-header">
          <div>
            <h1 className="page-title">Stock Library</h1>
            <p className="helper">
              Stock pools are built from Snowball interfaces in real time. Open any symbol to see its own page
              with kline, financial data, research reports, and earning forecasts.
            </p>
          </div>
          <div className="toolbar">
            <input
              className="input"
              type="text"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="Search by symbol, company, or sector"
            />
          </div>
        </div>
      </section>
      <MarketSection market="A" keyword={keyword} />
      <MarketSection market="HK" keyword={keyword} />
    </div>
  );
}
