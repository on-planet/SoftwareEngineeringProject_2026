import React, { useCallback, useMemo, useState } from "react";

import { useApiQuery } from "../hooks/useApiQuery";
import { getStockProfilePanel, StockProfileResponse } from "../services/api";
import {
  formatLoosePercent,
  formatNullableNumber,
  formatNumber,
  formatPercent,
  formatSigned,
  normalizePercentRatio,
} from "../utils/format";
import { getPrimaryStockName, getSecondaryStockName } from "../utils/stockNames";

const FALLBACK_SECTOR_LABEL = "未分类";
const STOCK_PROFILE_STALE_TIME_MS = 2 * 60 * 1000;
const STOCK_PROFILE_CACHE_TIME_MS = 10 * 60 * 1000;

const normalizeSector = (value?: string | null) => {
  const text = String(value ?? "").trim();
  if (!text || text.toLowerCase() === "unknown" || text === "未知") {
    return FALLBACK_SECTOR_LABEL;
  }
  return text;
};

type Props = {
  symbol: string;
};

type PankouLevel = {
  level: number;
  price?: number | null;
  volume?: number | null;
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
  const normalizedSymbol = useMemo(() => String(symbol || "").trim().toUpperCase(), [symbol]);
  const [liveRefreshing, setLiveRefreshing] = useState(false);

  const profileQuery = useApiQuery<StockProfileResponse>(
    normalizedSymbol ? ["stock-profile", normalizedSymbol] : null,
    () => getStockProfilePanel(normalizedSymbol, undefined, { cache: false }),
    {
      staleTimeMs: STOCK_PROFILE_STALE_TIME_MS,
      cacheTimeMs: STOCK_PROFILE_CACHE_TIME_MS,
      retry: 1,
    },
  );

  const profile = profileQuery.data ?? null;

  const handleRefreshLiveQuote = useCallback(async () => {
    if (!normalizedSymbol) {
      return;
    }
    setLiveRefreshing(true);
    try {
      await profileQuery.refetch(() =>
        getStockProfilePanel(
          normalizedSymbol,
          { prefer_live: true, refresh_key: Date.now() },
          { cache: false, retry: 1 },
        ),
      );
    } finally {
      setLiveRefreshing(false);
    }
  }, [normalizedSymbol, profileQuery]);

  const priceChange = useMemo(() => {
    const change = profile?.quote?.change;
    if (change === null || change === undefined || Number.isNaN(change)) {
      return null;
    }
    return change;
  }, [profile]);

  const changeColor = useMemo(() => {
    const change = priceChange ?? 0;
    return change < 0 ? "#10b981" : "#ef4444";
  }, [priceChange]);

  const percentRatio = useMemo(() => {
    const lastClose = profile?.quote?.last_close;
    if (
      priceChange !== null &&
      lastClose !== null &&
      lastClose !== undefined &&
      !Number.isNaN(lastClose) &&
      lastClose !== 0
    ) {
      return priceChange / lastClose;
    }
    return normalizePercentRatio(profile?.quote?.percent);
  }, [priceChange, profile]);

  if (!normalizedSymbol) {
    return <div className="card helper">正在读取股票代码...</div>;
  }

  if (profileQuery.isLoading) {
    return <div className="card helper">个股概览加载中...</div>;
  }

  if (profileQuery.error && !profile) {
    return <div className="card helper">{`个股概览加载失败：${profileQuery.error.message}`}</div>;
  }

  if (!profile) {
    return <div className="card helper">暂无个股概览数据。</div>;
  }

  const quote = profile.quote ?? null;
  const detail = profile.quote_detail ?? null;
  const pankou = profile.pankou ?? null;
  const fundamental = profile.fundamental ?? null;
  const extrasLoading = profileQuery.isFetching && (!detail || !pankou);
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
            {profile.symbol} · {profile.market} · {normalizeSector(profile.sector)}
          </div>
          {quote?.timestamp ? (
            <div className="helper" style={{ marginTop: 6 }}>
              行情时间：{new Date(quote.timestamp).toLocaleString("zh-CN")}
            </div>
          ) : null}
          <div style={{ marginTop: 12 }}>
            <button
              type="button"
              className="input"
              onClick={() => {
                void handleRefreshLiveQuote();
              }}
              disabled={liveRefreshing}
            >
              {liveRefreshing ? "实时行情刷新中..." : "获取实时行情"}
            </button>
          </div>
        </div>
        <div className="quote-hero">
          <div className="quote-current">{formatNullableNumber(quote?.current)}</div>
          <div className="quote-change" style={{ color: changeColor }}>
            {priceChange !== null ? formatSigned(priceChange) : "--"}
            <span style={{ marginLeft: 8 }}>{percentRatio !== null ? formatPercent(percentRatio) : "--"}</span>
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
        <MetricCard title="换手率" value={formatLoosePercent(quote?.turnover_rate)} />
        <MetricCard title="振幅" value={formatLoosePercent(quote?.amplitude)} />
        <MetricCard title="市盈率 TTM" value={formatNullableNumber(detail?.pe_ttm)} helper={extrasLoading && !detail ? "补充中" : undefined} />
        <MetricCard title="市净率" value={formatNullableNumber(detail?.pb)} helper={extrasLoading && !detail ? "补充中" : undefined} />
        <MetricCard title="市销率 TTM" value={formatNullableNumber(detail?.ps_ttm)} helper={extrasLoading && !detail ? "补充中" : undefined} />
        <MetricCard title="市现率" value={formatNullableNumber(detail?.pcf)} helper={extrasLoading && !detail ? "补充中" : undefined} />
        <MetricCard title="总市值" value={detail?.market_cap !== null && detail?.market_cap !== undefined ? formatNumber(detail.market_cap) : "--"} helper={extrasLoading && !detail ? "补充中" : undefined} />
        <MetricCard title="流通市值" value={detail?.float_market_cap !== null && detail?.float_market_cap !== undefined ? formatNumber(detail.float_market_cap) : "--"} helper={extrasLoading && !detail ? "补充中" : undefined} />
        <MetricCard title="股息率" value={formatLoosePercent(detail?.dividend_yield)} helper={extrasLoading && !detail ? "补充中" : undefined} />
        <MetricCard title="量比" value={formatNullableNumber(detail?.volume_ratio)} helper={extrasLoading && !detail ? "补充中" : undefined} />
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
            <MetricCard title="委比" value={formatLoosePercent(pankou?.ratio)} />
            <MetricCard
              title="盘口时间"
              value={pankou?.timestamp ? new Date(pankou.timestamp).toLocaleTimeString("zh-CN", { hour12: false }) : "--"}
            />
            <MetricCard
              title="最小交易单位"
              value={detail?.lot_size !== null && detail?.lot_size !== undefined ? formatNumber(detail.lot_size) : "--"}
              helper={extrasLoading && !detail ? "补充中" : undefined}
            />
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
