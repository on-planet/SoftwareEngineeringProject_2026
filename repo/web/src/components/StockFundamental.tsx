import React, { useEffect, useMemo, useState } from "react";

import { getFundamental, getStock } from "../services/api";
import { formatNullableNumber, formatNumber, formatSigned, formatSmartPercent } from "../utils/format";
import { getPrimaryStockName, getSecondaryStockName } from "../utils/stockNames";

type Quote = {
  current?: number | null;
  change?: number | null;
  percent?: number | null;
  open?: number | null;
  high?: number | null;
  low?: number | null;
  last_close?: number | null;
  volume?: number | null;
  amount?: number | null;
  turnover_rate?: number | null;
  amplitude?: number | null;
  timestamp?: string | null;
};

type QuoteDetail = {
  pe_ttm?: number | null;
  pb?: number | null;
  ps_ttm?: number | null;
  pcf?: number | null;
  market_cap?: number | null;
  float_market_cap?: number | null;
  dividend_yield?: number | null;
  volume_ratio?: number | null;
  lot_size?: number | null;
};

type PankouLevel = {
  level: number;
  price?: number | null;
  volume?: number | null;
};

type Pankou = {
  diff?: number | null;
  ratio?: number | null;
  timestamp?: string | null;
  bids?: PankouLevel[];
  asks?: PankouLevel[];
};

type StockProfile = {
  symbol: string;
  name: string;
  market: string;
  sector: string;
  quote?: Quote | null;
  quote_detail?: QuoteDetail | null;
  pankou?: Pankou | null;
};

type Fundamental = {
  symbol: string;
  score: number;
  summary: string;
  updated_at: string;
} | null;

type Props = {
  symbol: string;
};

function MetricCard({ title, value, helper }: { title: string; value: string; helper?: string }) {
  return (
    <div className="metric-card">
      <div className="helper">{title}</div>
      <div className="metric-value">{value}</div>
      {helper ? <div className="metric-helper">{helper}</div> : null}
    </div>
  );
}

function DepthTable({ title, prefix, items }: { title: string; prefix: string; items: PankouLevel[] }) {
  return (
    <div className="depth-card">
      <div className="card-title">{title}</div>
      {!items.length ? (
        <div className="helper">暂无盘口数据</div>
      ) : (
        <table className="depth-table">
          <thead>
            <tr>
              <th>档位</th>
              <th>价格</th>
              <th>数量</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={`${prefix}-${item.level}`}>
                <td>{prefix}{item.level}</td>
                <td>{formatNullableNumber(item.price)}</td>
                <td>{item.volume !== null && item.volume !== undefined ? formatNumber(item.volume) : "--"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function StockFundamental({ symbol }: Props) {
  const [profile, setProfile] = useState<StockProfile | null>(null);
  const [fundamental, setFundamental] = useState<Fundamental>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    Promise.all([getStock(symbol), getFundamental(symbol)])
      .then(([profileRes, fundamentalRes]) => {
        if (!active) {
          return;
        }
        setProfile(profileRes as StockProfile);
        setFundamental(fundamentalRes as Fundamental);
        setError(null);
      })
      .catch((err: Error) => {
        if (!active) {
          return;
        }
        setError(err.message || "个股概览加载失败");
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

  const changeColor = useMemo(() => {
    const change = profile?.quote?.change ?? 0;
    return change < 0 ? "#10b981" : "#ef4444";
  }, [profile]);

  if (loading) {
    return <div className="card helper">个股概览加载中...</div>;
  }

  if (error) {
    return <div className="card helper">个股概览加载失败：{error}</div>;
  }

  if (!profile) {
    return <div className="card helper">暂无个股概览数据。</div>;
  }

  const quote = profile.quote ?? null;
  const detail = profile.quote_detail ?? null;
  const pankou = profile.pankou ?? null;
  const primaryName = getPrimaryStockName(profile.symbol, profile.name);
  const secondaryName = getSecondaryStockName(profile.symbol, profile.name);

  return (
    <div className="card">
      <div className="stock-profile-header">
        <div>
          <div className="stock-profile-title">{primaryName}</div>
          {secondaryName ? (
            <div className="helper" style={{ marginTop: 6 }}>
              {secondaryName}
            </div>
          ) : null}
          <div className="helper" style={{ marginTop: 6 }}>
            {profile.symbol} · {profile.market} · {profile.sector || "未分类"}
          </div>
          {quote?.timestamp ? (
            <div className="helper" style={{ marginTop: 6 }}>
              行情时间：{new Date(quote.timestamp).toLocaleString("zh-CN")}
            </div>
          ) : null}
        </div>
        <div className="quote-hero">
          <div className="quote-current">{formatNullableNumber(quote?.current)}</div>
          <div className="quote-change" style={{ color: changeColor }}>
            {quote?.change !== null && quote?.change !== undefined ? formatSigned(quote.change) : "--"}
            <span style={{ marginLeft: 8 }}>{formatSmartPercent(quote?.percent)}</span>
          </div>
        </div>
      </div>

      <div className="metric-grid" style={{ marginTop: 18 }}>
        <MetricCard title="今开" value={formatNullableNumber(quote?.open)} />
        <MetricCard title="最高" value={formatNullableNumber(quote?.high)} />
        <MetricCard title="最低" value={formatNullableNumber(quote?.low)} />
        <MetricCard title="昨收" value={formatNullableNumber(quote?.last_close)} />
        <MetricCard title="成交量" value={quote?.volume !== null && quote?.volume !== undefined ? formatNumber(quote.volume) : "--"} />
        <MetricCard title="成交额" value={quote?.amount !== null && quote?.amount !== undefined ? formatNumber(quote.amount) : "--"} />
        <MetricCard title="换手率" value={formatSmartPercent(quote?.turnover_rate)} />
        <MetricCard title="振幅" value={formatSmartPercent(quote?.amplitude)} />
        <MetricCard title="市盈率 TTM" value={formatNullableNumber(detail?.pe_ttm)} />
        <MetricCard title="市净率" value={formatNullableNumber(detail?.pb)} />
        <MetricCard title="市销率 TTM" value={formatNullableNumber(detail?.ps_ttm)} />
        <MetricCard title="市现率" value={formatNullableNumber(detail?.pcf)} />
        <MetricCard title="总市值" value={detail?.market_cap !== null && detail?.market_cap !== undefined ? formatNumber(detail.market_cap) : "--"} />
        <MetricCard title="流通市值" value={detail?.float_market_cap !== null && detail?.float_market_cap !== undefined ? formatNumber(detail.float_market_cap) : "--"} />
        <MetricCard title="股息率" value={formatSmartPercent(detail?.dividend_yield)} />
        <MetricCard title="量比" value={formatNullableNumber(detail?.volume_ratio)} />
      </div>

      <div className="summary-grid">
        <div className="summary-card">
          <div className="helper">基本面得分</div>
          <div className="stock-score-value">{fundamental ? formatNullableNumber(fundamental.score, 1) : "--"}</div>
          <div className="stock-summary">{fundamental?.summary ?? "暂无基本面摘要。"}</div>
          {fundamental?.updated_at ? (
            <div className="helper" style={{ marginTop: 12 }}>
              更新时间：{new Date(fundamental.updated_at).toLocaleString("zh-CN")}
            </div>
          ) : null}
        </div>
        <div className="summary-card">
          <div className="card-title">盘口概览</div>
          <div className="metric-grid compact-grid">
            <MetricCard title="委差" value={formatNullableNumber(pankou?.diff)} />
            <MetricCard title="委比" value={formatSmartPercent(pankou?.ratio)} />
            <MetricCard title="盘口时间" value={pankou?.timestamp ? new Date(pankou.timestamp).toLocaleTimeString("zh-CN", { hour12: false }) : "--"} />
            <MetricCard title="最小交易单位" value={detail?.lot_size !== null && detail?.lot_size !== undefined ? formatNumber(detail.lot_size) : "--"} />
          </div>
        </div>
      </div>

      <div className="depth-grid">
        <DepthTable title="卖盘五档" prefix="卖" items={pankou?.asks ?? []} />
        <DepthTable title="买盘五档" prefix="买" items={pankou?.bids ?? []} />
      </div>
    </div>
  );
}

