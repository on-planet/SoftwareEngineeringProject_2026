import Link from "next/link";
import React, { useEffect, useState } from "react";

import { getStocks } from "../services/api";
import { getPrimaryStockName, getSecondaryStockName } from "../utils/stockNames";

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
        setError(err.message || "股票列表加载失败");
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
        <h2 className="section-title">{market === "A" ? "A 股实时股票池" : "港股实时股票池"}</h2>
        <div className="helper">已加载 {items.length} 只</div>
      </div>
      {loading ? <div className="helper">股票列表加载中...</div> : null}
      {!loading && error ? <div className="helper">股票列表加载失败：{error}</div> : null}
      {!loading && !error ? (
        <div className="stock-grid">
          {items.map((item) => {
            const primaryName = getPrimaryStockName(item.symbol, item.name);
            const secondaryName = getSecondaryStockName(item.symbol, item.name);
            return (
              <Link key={item.symbol} href={`/stock/${encodeURIComponent(item.symbol)}`} className="stock-card">
                <div className="stock-card-title">{primaryName}</div>
                {secondaryName ? <div className="helper">{secondaryName}</div> : null}
                <div className="helper">{item.symbol}</div>
                <div className="stock-card-meta">
                  <span>{item.market}</span>
                  <span>{item.sector || "未分类"}</span>
                </div>
              </Link>
            );
          })}
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
            <h1 className="page-title">股票池</h1>
            <p className="helper">
              股票池由雪球接口实时生成。每只股票都可以进入独立详情页，查看实时快照、盘口、多周期 K 线、财报、研报和业绩预告。
            </p>
          </div>
          <div className="toolbar">
            <input
              className="input"
              type="text"
              value={keyword}
              onChange={(event) => setKeyword(event.target.value)}
              placeholder="按代码、名称或行业搜索"
            />
          </div>
        </div>
      </section>
      <MarketSection market="A" keyword={keyword} />
      <MarketSection market="HK" keyword={keyword} />
    </div>
  );
}
