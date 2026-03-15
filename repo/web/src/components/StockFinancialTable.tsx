import React, { useEffect, useState } from "react";

import { getStockFinancials } from "../services/api";
import { formatNumber } from "../utils/format";

type FinancialItem = {
  symbol: string;
  period: string;
  revenue: number;
  net_income: number;
  cash_flow: number;
  roe: number;
  debt_ratio: number;
};

type FinancialPage = {
  items: FinancialItem[];
  total: number;
  limit: number;
  offset: number;
};

type Props = {
  symbol: string;
};

export function StockFinancialTable({ symbol }: Props) {
  const [items, setItems] = useState<FinancialItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    getStockFinancials(symbol, { limit: 12, sort: "desc" })
      .then((res) => {
        if (!active) {
          return;
        }
        const payload = res as FinancialPage;
        setItems(payload.items ?? []);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setItems([]);
        setError(err.message || "Failed to load financials");
      })
      .finally(() => {
        if (active) {
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [symbol]);

  if (loading) {
    return <div className="helper">Loading financial statements...</div>;
  }

  if (error) {
    return <div className="helper">Financial statements failed: {error}</div>;
  }

  if (!items.length) {
    return <div className="helper">No financial statements available.</div>;
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table className="data-table">
        <thead>
          <tr>
            <th>Period</th>
            <th>Revenue</th>
            <th>Net Income</th>
            <th>Operating Cash Flow</th>
            <th>ROE</th>
            <th>Debt Ratio</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={`${item.symbol}-${item.period}`}>
              <td>{item.period}</td>
              <td>{formatNumber(item.revenue ?? 0)}</td>
              <td>{formatNumber(item.net_income ?? 0)}</td>
              <td>{formatNumber(item.cash_flow ?? 0)}</td>
              <td>{((item.roe ?? 0) * 100).toFixed(2)}%</td>
              <td>{((item.debt_ratio ?? 0) * 100).toFixed(2)}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
