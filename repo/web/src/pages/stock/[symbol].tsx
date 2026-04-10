import dynamic from "next/dynamic";
import { useRouter } from "next/router";
import React, { useEffect, useMemo, useState } from "react";

import { StockFundamental } from "../../components/StockFundamental";
import { StockSmokeButtCard } from "../../components/StockSmokeButtCard";
import { useApiQuery } from "../../hooks/useApiQuery";
import {
  buildMyWatchTargetsQueryKey,
  getMyWatchTargets,
  getUserScopedQueryOptions,
  primeApiQuery,
  upsertMyWatchTarget,
} from "../../services/api";
import { AUTH_CHANGED_EVENT, getAuthToken } from "../../utils/auth";
import { addWatchTarget, hasWatchTarget, readWatchTargets, replaceWatchTargets } from "../../utils/watchTargets";

const StockKlinePanel = dynamic(
  () => import("../../components/StockKlinePanel").then((mod) => mod.StockKlinePanel),
  { ssr: false, loading: () => <div className="card helper">K 线加载中...</div> },
);
const StockIndicatorsChart = dynamic(
  () => import("../../components/StockIndicatorsChart").then((mod) => mod.StockIndicatorsChart),
  { ssr: false, loading: () => <div className="helper">指标加载中...</div> },
);
const StockRiskChart = dynamic(
  () => import("../../components/StockRiskChart").then((mod) => mod.StockRiskChart),
  { ssr: false, loading: () => <div className="helper">风险视图加载中...</div> },
);
const StockFinancialTable = dynamic(
  () => import("../../components/StockFinancialTable").then((mod) => mod.StockFinancialTable),
  { ssr: false, loading: () => <div className="helper">财务数据加载中...</div> },
);
const StockResearchPanel = dynamic(
  () => import("../../components/StockResearchPanel").then((mod) => mod.StockResearchPanel),
  { ssr: false, loading: () => <div className="helper">研报加载中...</div> },
);

type Props = {
  symbol?: string;
};

type DeferredSectionProps = {
  children: React.ReactNode;
  placeholder: React.ReactNode;
  resetKey: string;
  minHeight?: number;
  rootMargin?: string;
};

function normalizeSymbol(value: string) {
  return (value || "").trim().toUpperCase();
}

function dedupeSymbols(values: string[]) {
  const unique = new Set<string>();
  const result: string[] = [];
  for (const value of values || []) {
    const symbol = normalizeSymbol(value);
    if (!symbol || unique.has(symbol)) {
      continue;
    }
    unique.add(symbol);
    result.push(symbol);
  }
  return result;
}

function parseSymbolFromAsPath(asPath: string) {
  const rawPath = String(asPath || "").split("?")[0].split("#")[0];
  const segments = rawPath.split("/").filter(Boolean);
  const raw = segments[segments.length - 1] || "";
  if (!raw || raw.toLowerCase() === "stock" || raw.includes("[")) {
    return "";
  }
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}

function DeferredSection({
  children,
  placeholder,
  resetKey,
  minHeight = 160,
  rootMargin = "280px 0px",
}: DeferredSectionProps) {
  const [visible, setVisible] = useState(false);
  const [node, setNode] = useState<HTMLDivElement | null>(null);

  useEffect(() => {
    setVisible(false);
  }, [resetKey]);

  useEffect(() => {
    if (visible || !node) {
      return;
    }
    if (typeof window === "undefined" || typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [node, rootMargin, visible]);

  return (
    <div ref={setNode} style={!visible ? { minHeight } : undefined}>
      {visible ? children : placeholder}
    </div>
  );
}

export default function StockPage({ symbol }: Props) {
  const router = useRouter();
  const routeSymbol = useMemo(() => {
    if (typeof router.query.symbol === "string" && router.query.symbol.trim()) {
      return router.query.symbol;
    }
    const fromPath = parseSymbolFromAsPath(router.asPath || "");
    if (fromPath) {
      return fromPath;
    }
    return symbol || "";
  }, [router.asPath, router.query.symbol, symbol]);
  const normalizedRouteSymbol = useMemo(() => normalizeSymbol(routeSymbol), [routeSymbol]);
  const [currentSymbol, setCurrentSymbol] = useState(normalizedRouteSymbol);
  const [watchMessage, setWatchMessage] = useState<string | null>(null);
  const [isWatched, setIsWatched] = useState(false);
  const [authToken, setAuthToken] = useState<string | null>(null);
  const watchTargetsQueryKey = useMemo(
    () => (authToken ? buildMyWatchTargetsQueryKey(authToken) : null),
    [authToken],
  );
  const watchTargetsQuery = useApiQuery(
    watchTargetsQueryKey,
    () => getMyWatchTargets(authToken as string),
    getUserScopedQueryOptions("watch-targets"),
  );

  useEffect(() => {
    if (!normalizedRouteSymbol) {
      return;
    }
    setCurrentSymbol(normalizedRouteSymbol);
    setWatchMessage(null);
  }, [normalizedRouteSymbol]);

  const appliedSymbol = normalizeSymbol(currentSymbol) || normalizedRouteSymbol;
  const activeSymbol = normalizeSymbol(appliedSymbol);

  useEffect(() => {
    if (!activeSymbol) {
      setIsWatched(false);
      return;
    }
    setIsWatched(hasWatchTarget(activeSymbol));
  }, [activeSymbol]);

  useEffect(() => {
    const syncToken = () => {
      setAuthToken(getAuthToken());
    };
    syncToken();
    window.addEventListener(AUTH_CHANGED_EVENT, syncToken);
    return () => {
      window.removeEventListener(AUTH_CHANGED_EVENT, syncToken);
    };
  }, []);

  useEffect(() => {
    if (!authToken) {
      return;
    }
    const remoteSymbols = dedupeSymbols(
      (watchTargetsQuery.data || []).map((item: any) => String(item?.symbol || "")),
    );
    const merged = dedupeSymbols([...remoteSymbols, ...readWatchTargets()]);
    const next = replaceWatchTargets(merged);
    setIsWatched(next.includes(activeSymbol));
  }, [activeSymbol, authToken, watchTargetsQuery.data]);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const nextSymbol = normalizeSymbol(currentSymbol);
    if (!nextSymbol) {
      return;
    }
    void router.push(`/stock/${encodeURIComponent(nextSymbol)}`);
  };

  const handleAddWatchTarget = () => {
    const targetSymbol = normalizeSymbol(activeSymbol);
    if (!targetSymbol) {
      return;
    }
    const nextTargets = addWatchTarget(targetSymbol);
    setIsWatched(true);
    setWatchMessage(`已加入自选：${targetSymbol}`);
    if (watchTargetsQueryKey) {
      primeApiQuery(
        watchTargetsQueryKey,
        nextTargets.map((item) => ({ symbol: item })),
        getUserScopedQueryOptions("watch-targets"),
      );
    }
    if (authToken) {
      void upsertMyWatchTarget(authToken, targetSymbol).catch(() => {
        setWatchMessage(`已本地保存，远程同步失败：${targetSymbol}`);
      });
    }
  };

  return (
    <div className="page">
      <section className="card">
        <div className="page-header">
          <div>
            <h1 className="page-title">个股详情</h1>
            <p className="helper">
              首屏优先加载关键行情和评分数据。K线、财务、研报和图表将在页面就绪后延迟加载。
            </p>
          </div>
          <form className="toolbar" onSubmit={handleSubmit}>
            <input
              className="input"
              type="text"
              value={currentSymbol}
              onChange={(event) => setCurrentSymbol(event.target.value)}
              placeholder="输入代码，例如 600000、000001.SZ、0700.HK"
            />
            <button type="submit" className="primary-button">
              打开
            </button>
            <button
              type="button"
              className="primary-button"
              onClick={handleAddWatchTarget}
              disabled={isWatched}
            >
              {isWatched ? "已在自选" : "加入自选"}
            </button>
          </form>
          {watchMessage ? <div className="helper">{watchMessage}</div> : null}
        </div>
      </section>

      {activeSymbol ? (
        <>
          <section>
            <StockFundamental symbol={activeSymbol} />
          </section>

          <section>
            <StockSmokeButtCard symbol={activeSymbol} />
          </section>

          <section>
            <DeferredSection
              resetKey={activeSymbol}
              minHeight={320}
              placeholder={<div className="card helper">正在准备 K 线...</div>}
            >
              <StockKlinePanel symbol={activeSymbol} />
            </DeferredSection>
          </section>

          <section className="split-grid">
            <div>
              <h2 className="section-title">技术指标</h2>
              <DeferredSection
                resetKey={activeSymbol}
                minHeight={320}
                placeholder={<div className="card helper">正在准备指标...</div>}
              >
                <div className="card">
                  <StockIndicatorsChart symbol={activeSymbol} />
                </div>
              </DeferredSection>
            </div>
            <div>
              <h2 className="section-title">风险分析</h2>
              <DeferredSection
                resetKey={activeSymbol}
                minHeight={320}
                placeholder={<div className="card helper">正在准备风险视图...</div>}
              >
                <div className="card">
                  <StockRiskChart symbol={activeSymbol} />
                </div>
              </DeferredSection>
            </div>
          </section>

          <section>
            <h2 className="section-title">财务数据</h2>
            <DeferredSection
              resetKey={activeSymbol}
              minHeight={320}
              placeholder={<div className="card helper">正在准备财务数据...</div>}
            >
              <div className="card">
                <StockFinancialTable symbol={activeSymbol} />
              </div>
            </DeferredSection>
          </section>

          <section>
            <h2 className="section-title">研究报告</h2>
            <DeferredSection
              resetKey={activeSymbol}
              minHeight={320}
              placeholder={<div className="card helper">正在准备研报...</div>}
            >
              <div className="card">
                <StockResearchPanel symbol={activeSymbol} />
              </div>
            </DeferredSection>
          </section>
        </>
      ) : (
        <section>
          <div className="card helper">加载代码中...</div>
        </section>
      )}
    </div>
  );
}
