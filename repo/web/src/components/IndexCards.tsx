import React, { useEffect, useState } from "react";

import { getIndices } from "../services/api";
import { formatNumber, formatSigned } from "../utils/format";

type IndexItem = {
  symbol: string;
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

export function IndexCards({ asOf }: { asOf?: string }) {
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
        setError(err.message || "加载指数失败");
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

  if (loading) {
    return <div>指数加载中...</div>;
  }

  if (error) {
    return <div>指数加载失败：{error}</div>;
  }

  if (data.length === 0) {
    return <div>暂无指数数据</div>;
  }

  return (
    <div style={{ display: "grid", gap: 16, gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))" }}>
      {data.map((item) => {
        const changeColor = item.change >= 0 ? "#d64545" : "#2c7a7b";
        return (
          <div
            key={`${item.symbol}-${item.date}`}
            style={{
              border: "1px solid #e2e8f0",
              borderRadius: 8,
              padding: 12,
              background: "#fff",
              boxShadow: "0 1px 2px rgba(0,0,0,0.06)",
            }}
          >
            <div style={{ fontWeight: 600 }}>{item.symbol}</div>
            <div style={{ fontSize: 12, color: "#718096" }}>{item.date}</div>
            <div style={{ marginTop: 8, fontSize: 18 }}>{formatNumber(item.close)}</div>
            <div style={{ marginTop: 4, color: changeColor }}>{formatSigned(item.change)}</div>
          </div>
        );
      })}
    </div>
  );
}
