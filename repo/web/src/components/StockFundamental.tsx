import React, { useCallback, useEffect, useMemo, useState } from "react";

import { useApiQuery } from "../hooks/useApiQuery";
import {
  buildStockExtrasQueryKey,
  buildStockOverviewQueryKey,
  getStockExtras,
  getStockExtrasQueryOptions,
  getStockOverview,
  getStockOverviewQueryOptions,
  StockExtrasResponse,
  StockOverviewResponse,
} from "../services/api";
import {
  formatLoosePercent,
  formatNullableNumber,
  formatNumber,
  formatPercent,
  formatSigned,
  normalizePercentRatio,
} from "../utils/format";
import { getPrimaryStockName, getSecondaryStockName } from "../utils/stockNames";

const FALLBACK_SECTOR_LABEL = "Unclassified";

const normalizeSector = (value?: string | null) => {
  const text = String(value ?? "").trim();
  if (!text || text.toLowerCase() === "unknown") {
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
        <div className="helper">No depth data</div>
      ) : (
        <table className="depth-table">
          <thead>
            <tr>
              <th>Level</th>
              <th>Price</th>
              <th>Volume</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={`${prefix}-${item.level}`}>
                <td>
                  {prefix}
                  {item.level}
                </td>
                <td>{formatNullableNumber(item.price)}</td>
                <td>
                  {item.volume !== null && item.volume !== undefined
                    ? formatNumber(item.volume)
                    : "--"}
                </td>
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
  const [shouldLoadExtras, setShouldLoadExtras] = useState(false);

  const overviewCacheKey = useMemo(
    () => (normalizedSymbol ? buildStockOverviewQueryKey(normalizedSymbol) : null),
    [normalizedSymbol],
  );
  const extrasCacheKey = useMemo(
    () => (normalizedSymbol ? buildStockExtrasQueryKey(normalizedSymbol) : null),
    [normalizedSymbol],
  );

  useEffect(() => {
    if (!normalizedSymbol || typeof window === "undefined") {
      setShouldLoadExtras(false);
      return;
    }
    setShouldLoadExtras(false);

    let timeoutId: number | null = null;
    let idleId: number | null = null;
    const loadExtras = () => setShouldLoadExtras(true);
    const windowWithIdle = window as Window & {
      requestIdleCallback?: (
        callback: IdleRequestCallback,
        options?: IdleRequestOptions,
      ) => number;
      cancelIdleCallback?: (handle: number) => void;
    };

    if (typeof windowWithIdle.requestIdleCallback === "function") {
      idleId = windowWithIdle.requestIdleCallback(() => loadExtras(), { timeout: 500 });
    } else {
      timeoutId = window.setTimeout(loadExtras, 180);
    }

    return () => {
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
      if (idleId !== null && typeof windowWithIdle.cancelIdleCallback === "function") {
        windowWithIdle.cancelIdleCallback(idleId);
      }
    };
  }, [normalizedSymbol]);

  const overviewQuery = useApiQuery<StockOverviewResponse>(
    overviewCacheKey,
    () => getStockOverview(normalizedSymbol),
    overviewCacheKey ? getStockOverviewQueryOptions(overviewCacheKey) : undefined,
  );
  const extrasQuery = useApiQuery<StockExtrasResponse>(
    shouldLoadExtras ? extrasCacheKey : null,
    () => getStockExtras(normalizedSymbol),
    extrasCacheKey ? getStockExtrasQueryOptions(extrasCacheKey) : undefined,
  );

  const profile = overviewQuery.data ?? null;
  const extras = extrasQuery.data ?? null;

  const handleRefreshLiveQuote = useCallback(async () => {
    if (!normalizedSymbol) {
      return;
    }
    setLiveRefreshing(true);
    setShouldLoadExtras(true);
    try {
      const refreshKey = Date.now();
      const tasks: Array<Promise<unknown>> = [
        overviewQuery.refetch(() =>
          getStockOverview(normalizedSymbol, {
            prefer_live: true,
            refresh_key: refreshKey,
          }),
        ),
      ];
      if (shouldLoadExtras) {
        tasks.push(
          extrasQuery.refetch(() =>
            getStockExtras(normalizedSymbol, {
              prefer_live: true,
              refresh_key: refreshKey,
            }),
          ),
        );
      }
      await Promise.all(tasks);
    } finally {
      setLiveRefreshing(false);
    }
  }, [extrasQuery, normalizedSymbol, overviewQuery, shouldLoadExtras]);

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
    return <div className="card helper">Loading symbol...</div>;
  }

  if (overviewQuery.isLoading && !profile) {
    return <div className="card helper">Loading stock overview...</div>;
  }

  if (overviewQuery.error && !profile) {
    return (
      <div className="card helper">
        {`Failed to load stock overview: ${overviewQuery.error.message}`}
      </div>
    );
  }

  if (!profile) {
    return <div className="card helper">No stock overview data.</div>;
  }

  const quote = profile.quote ?? null;
  const detail = extras?.quote_detail ?? null;
  const pankou = extras?.pankou ?? null;
  const fundamental = profile.fundamental ?? null;
  const extrasLoading =
    shouldLoadExtras &&
    (extrasQuery.isLoading || extrasQuery.isFetching) &&
    (!detail || !pankou);
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
            {profile.symbol} | {profile.market} | {normalizeSector(profile.sector)}
          </div>
          {quote?.timestamp ? (
            <div className="helper" style={{ marginTop: 6 }}>
              Quote time: {new Date(quote.timestamp).toLocaleString("zh-CN")}
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
              {liveRefreshing ? "Refreshing live quote..." : "Refresh live quote"}
            </button>
          </div>
        </div>
        <div className="quote-hero">
          <div className="quote-current">{formatNullableNumber(quote?.current)}</div>
          <div className="quote-change" style={{ color: changeColor }}>
            {priceChange !== null ? formatSigned(priceChange) : "--"}
            <span style={{ marginLeft: 8 }}>
              {percentRatio !== null ? formatPercent(percentRatio) : "--"}
            </span>
          </div>
        </div>
      </div>

      <div className="metric-grid" style={{ marginTop: 18 }}>
        <MetricCard title="Open" value={formatNullableNumber(quote?.open)} />
        <MetricCard title="High" value={formatNullableNumber(quote?.high)} />
        <MetricCard title="Low" value={formatNullableNumber(quote?.low)} />
        <MetricCard title="Prev close" value={formatNullableNumber(quote?.last_close)} />
        <MetricCard
          title="Volume"
          value={
            quote?.volume !== null && quote?.volume !== undefined
              ? formatNumber(quote.volume)
              : "--"
          }
        />
        <MetricCard
          title="Turnover"
          value={
            quote?.amount !== null && quote?.amount !== undefined
              ? formatNumber(quote.amount)
              : "--"
          }
        />
        <MetricCard title="Turnover rate" value={formatLoosePercent(quote?.turnover_rate)} />
        <MetricCard title="Amplitude" value={formatLoosePercent(quote?.amplitude)} />
        <MetricCard
          title="PE TTM"
          value={formatNullableNumber(detail?.pe_ttm)}
          helper={extrasLoading && !detail ? "Loading..." : undefined}
        />
        <MetricCard
          title="PB"
          value={formatNullableNumber(detail?.pb)}
          helper={extrasLoading && !detail ? "Loading..." : undefined}
        />
        <MetricCard
          title="PS TTM"
          value={formatNullableNumber(detail?.ps_ttm)}
          helper={extrasLoading && !detail ? "Loading..." : undefined}
        />
        <MetricCard
          title="PCF"
          value={formatNullableNumber(detail?.pcf)}
          helper={extrasLoading && !detail ? "Loading..." : undefined}
        />
        <MetricCard
          title="Market cap"
          value={
            detail?.market_cap !== null && detail?.market_cap !== undefined
              ? formatNumber(detail.market_cap)
              : "--"
          }
          helper={extrasLoading && !detail ? "Loading..." : undefined}
        />
        <MetricCard
          title="Float cap"
          value={
            detail?.float_market_cap !== null && detail?.float_market_cap !== undefined
              ? formatNumber(detail.float_market_cap)
              : "--"
          }
          helper={extrasLoading && !detail ? "Loading..." : undefined}
        />
        <MetricCard
          title="Dividend yield"
          value={formatLoosePercent(detail?.dividend_yield)}
          helper={extrasLoading && !detail ? "Loading..." : undefined}
        />
        <MetricCard
          title="Volume ratio"
          value={formatNullableNumber(detail?.volume_ratio)}
          helper={extrasLoading && !detail ? "Loading..." : undefined}
        />
      </div>

      <div className="summary-grid">
        <div className="summary-card">
          <div className="helper">Fundamental score</div>
          <div className="stock-score-value">
            {fundamental ? formatNullableNumber(fundamental.score, 1) : "--"}
          </div>
          <div className="stock-summary">
            {fundamental?.summary ?? "No fundamental summary."}
          </div>
          {fundamental?.updated_at ? (
            <div className="helper" style={{ marginTop: 12 }}>
              Updated: {new Date(fundamental.updated_at).toLocaleString("zh-CN")}
            </div>
          ) : null}
        </div>
        <div className="summary-card">
          <div className="card-title">Order book</div>
          <div className="metric-grid compact-grid">
            <MetricCard title="Diff" value={formatNullableNumber(pankou?.diff)} />
            <MetricCard title="Ratio" value={formatLoosePercent(pankou?.ratio)} />
            <MetricCard
              title="Book time"
              value={
                pankou?.timestamp
                  ? new Date(pankou.timestamp).toLocaleTimeString("zh-CN", { hour12: false })
                  : "--"
              }
            />
            <MetricCard
              title="Lot size"
              value={
                detail?.lot_size !== null && detail?.lot_size !== undefined
                  ? formatNumber(detail.lot_size)
                  : "--"
              }
              helper={extrasLoading && !detail ? "Loading..." : undefined}
            />
          </div>
        </div>
      </div>

      <div className="depth-grid">
        <DepthTable title="Ask depth" prefix="Ask " items={pankou?.asks ?? []} />
        <DepthTable title="Bid depth" prefix="Bid " items={pankou?.bids ?? []} />
      </div>
    </div>
  );
}
