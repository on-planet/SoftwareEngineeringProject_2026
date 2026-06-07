import Link from "next/link";
import React, { useMemo } from "react";

import { buildCigarbuttQueryKey, loadCigarbuttAnalysis, normalizeStrategySymbol } from "../domain/strategyScore";
import { useApiQuery } from "../hooks/useApiQuery";
import { CigarbuttAnalysisPanel } from "./CigarbuttAnalysisPanel";

type Props = {
  symbol: string;
};

type CigarbuttAnalysisResponse = {
  symbol: string;
  stock_price?: number | null;
  analysis: Record<string, unknown>;
};

export function StockCigarbuttCard({ symbol }: Props) {
  const normalizedSymbol = useMemo(() => normalizeStrategySymbol(symbol), [symbol]);
  const query = useApiQuery<CigarbuttAnalysisResponse>(
    normalizedSymbol ? buildCigarbuttQueryKey(normalizedSymbol) : null,
    () => loadCigarbuttAnalysis(normalizedSymbol),
    { staleTimeMs: 0, cacheTimeMs: 0, retry: 0, label: "cigarbutt-analysis" },
  );

  if (!normalizedSymbol) {
    return null;
  }

  if (query.isLoading && !query.data) {
    return <div className="card helper">静态价值型烟蒂股分析加载中...</div>;
  }

  if (query.error && !query.data) {
    return (
      <div className="card strategy-card">
        <div className="stock-profile-header">
          <div>
            <div className="card-title">静态价值型烟蒂股</div>
            <div className="helper">当前个股暂时无法生成静态价值分析。</div>
          </div>
          <Link href="/strategy/smoke-butt" className="badge-link">
            打开策略页
          </Link>
        </div>
      </div>
    );
  }

  if (!query.data?.analysis) {
    return null;
  }

  return (
    <div className="card strategy-card">
      <CigarbuttAnalysisPanel data={query.data} compact />
      <div style={{ marginTop: 14 }}>
        <Link href={`/strategy/smoke-butt?symbol=${encodeURIComponent(normalizedSymbol)}&tab=cigarbutt`} className="badge-link">
          打开完整分析
        </Link>
      </div>
    </div>
  );
}
