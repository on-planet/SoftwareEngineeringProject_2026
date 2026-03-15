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
        setError(err.message || "Failed to load indices");
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
    return <div className="helper">Loading indices...</div>;
  }

  if (error) {
    return <div className="helper">Indices failed: {error}</div>;
  }

  if (data.length === 0) {
    return <div className="helper">No index data available.</div>;
  }

  return (
    <div className="grid grid-3">
      {data.map((item) => {
        const changeColor = item.change >= 0 ? "#ef4444" : "#10b981";
        return (
          <div key={`${item.symbol}-${item.date}`} className="card">
            <div className="card-title">{item.symbol}</div>
            <div className="helper">{item.date}</div>
            <div style={{ marginTop: 8, fontSize: 20, fontWeight: 700 }}>{formatNumber(item.close)}</div>
            <div style={{ marginTop: 4, color: changeColor, fontWeight: 600 }}>{formatSigned(item.change)}</div>
          </div>
        );
      })}
    </div>
  );
}
