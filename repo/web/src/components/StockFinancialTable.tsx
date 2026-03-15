import React, { useEffect, useState } from "react";

import { getStockFinancials } from "../services/api";
import { formatNullableNumber, formatSmartPercent } from "../utils/format";

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
        setError(err.message || "财务报表加载失败");
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
    return <div className="helper">财务报表加载中...</div>;
  }

  if (error) {
    return <div className="helper">财务报表加载失败：{error}</div>;
  }

  if (!items.length) {
    return <div className="helper">暂无财务报表数据。</div>;
  }

  return (
    <div style={{ overflowX: "auto" }}>
      <table className="data-table">
        <thead>
          <tr>
            <th>报告期</th>
            <th>营业收入</th>
            <th>净利润</th>
            <th>经营现金流</th>
            <th>ROE</th>
            <th>资产负债率</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={`${item.symbol}-${item.period}`}>
              <td>{item.period}</td>
              <td>{formatNullableNumber(item.revenue, 0)}</td>
              <td>{formatNullableNumber(item.net_income, 0)}</td>
              <td>{formatNullableNumber(item.cash_flow, 0)}</td>
              <td>{formatSmartPercent(item.roe)}</td>
              <td>{formatSmartPercent(item.debt_ratio)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
