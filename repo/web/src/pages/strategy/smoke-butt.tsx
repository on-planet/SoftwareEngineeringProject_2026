import dynamic from "next/dynamic";
import Link from "next/link";
import React, { useEffect, useMemo, useState } from "react";

import { VirtualTable } from "../../components/virtual/VirtualTable";
import {
  buildStrategySignalExplanation,
  buildStrategyLeaderboardQueryKey,
  getStrategyScoreQueryOptions,
  loadStrategyLeaderboard,
  retrainStrategyScore,
} from "../../domain/strategyScore";
import { useApiQuery } from "../../hooks/useApiQuery";
import {
  SmokeButtListResponse,
  StrategySignal,
} from "../../services/api";
import { formatNullableNumber, formatPercent } from "../../utils/format";

const PAGE_SIZE = 100;
const SmokeButtBacktestPanel = dynamic(
  () => import("../../components/SmokeButtBacktestPanel").then((module) => module.SmokeButtBacktestPanel),
  {
    ssr: false,
    loading: () => <div className="helper">Preparing backtest panel...</div>,
  },
);

const SIGNAL_OPTIONS: Array<{ value: "" | StrategySignal; label: string }> = [
  { value: "", label: "All Signals" },
  { value: "strong_buy", label: "Strong Buy" },
  { value: "buy", label: "Buy" },
  { value: "watch", label: "Watch" },
  { value: "avoid", label: "Avoid" },
];

function signalTone(signal?: string | null) {
  if (signal === "strong_buy" || signal === "buy") {
    return "positive";
  }
  if (signal === "avoid") {
    return "negative";
  }
  return "neutral";
}

function signalLabel(signal?: string | null) {
  const target = SIGNAL_OPTIONS.find((item) => item.value === signal);
  return target?.label ?? signal ?? "--";
}

type DeferredSectionProps = {
  children: React.ReactNode;
  placeholder: React.ReactNode;
  resetKey: string;
  minHeight?: number;
  rootMargin?: string;
};

function DeferredSection({
  children,
  placeholder,
  resetKey,
  minHeight = 180,
  rootMargin = "320px 0px",
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

export default function SmokeButtStrategyPage() {
  const [market, setMarket] = useState<"" | "A" | "HK" | "US">("");
  const [signal, setSignal] = useState<"" | StrategySignal>("");
  const [page, setPage] = useState(1);
  const [isTraining, setIsTraining] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const offset = useMemo(() => (page - 1) * PAGE_SIZE, [page]);
  const listQuery = useApiQuery<SmokeButtListResponse>(
    buildStrategyLeaderboardQueryKey(market, signal, page),
    () => loadStrategyLeaderboard(market, signal, PAGE_SIZE, offset),
    getStrategyScoreQueryOptions("strategy-score-leaderboard"),
  );

  const run = listQuery.data?.run ?? null;
  const items = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const handleTrain = async () => {
    setIsTraining(true);
    setNotice(null);
    try {
      const response = await retrainStrategyScore();
      setNotice(
        `Training finished: ${response.run.as_of} | train rows ${response.run.train_rows} | scored ${response.run.scored_rows}`,
      );
      await listQuery.refetch(() => loadStrategyLeaderboard(market, signal, PAGE_SIZE, 0));
      setPage(1);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Training failed");
    } finally {
      setIsTraining(false);
    }
  };

  return (
    <div className="page">
      <section className="card hero-card">
        <div className="page-header">
          <div>
            <h1 className="page-title">AutoGluon Smoke Butt Strategy</h1>
            <p className="helper">
              Historical prices, fundamentals, events, buybacks, and research are ranked into a cross-sectional idea board.
            </p>
          </div>
          <div className="toolbar">
            <button type="button" className="primary-button" onClick={() => void handleTrain()} disabled={isTraining}>
              {isTraining ? "Training..." : "Retrain"}
            </button>
          </div>
        </div>
        <div className="hero-grid">
          <div className="hero-metric">
            <div className="card-title">Status</div>
            <div className="hero-metric-value">{run ? "Ready" : "Not Trained"}</div>
            <div className="helper">{run ? `Latest run: ${run.as_of}` : "Run the model to generate the board."}</div>
          </div>
          <div className="hero-metric">
            <div className="card-title">Train Rows</div>
            <div className="hero-metric-value">{run ? formatNullableNumber(run.train_rows, 0) : "--"}</div>
            <div className="helper">Rows used for model fitting</div>
          </div>
          <div className="hero-metric">
            <div className="card-title">Scored Symbols</div>
            <div className="hero-metric-value">{run ? formatNullableNumber(run.scored_rows, 0) : "--"}</div>
            <div className="helper">Symbols with fresh signals</div>
          </div>
        </div>
        {notice ? <div className="helper">{notice}</div> : null}
      </section>

      <section className="card">
        <div className="toolbar">
          <select
            className="select"
            value={market}
            onChange={(event) => {
              setMarket(event.target.value as "" | "A" | "HK" | "US");
              setPage(1);
            }}
          >
            <option value="">All Markets</option>
            <option value="A">A-share</option>
            <option value="HK">HK</option>
            <option value="US">US</option>
          </select>
          <select
            className="select"
            value={signal}
            onChange={(event) => {
              setSignal(event.target.value as "" | StrategySignal);
              setPage(1);
            }}
          >
            {SIGNAL_OPTIONS.map((item) => (
              <option key={item.label} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>

        {run ? (
          <div className="strategy-board-meta">
            <div className="helper">
              {`Trained at ${new Date(run.trained_at).toLocaleString("zh-CN")} | horizon ${run.label_horizon} trading days`}
            </div>
            <div className="strategy-pill-row">
              {run.feature_importance.slice(0, 5).map((item) => (
                <span key={item.feature} className="strategy-pill" data-tone="neutral">
                  {item.feature}
                  {item.importance !== null && item.importance !== undefined
                    ? ` | ${formatNullableNumber(item.importance, 2)}`
                    : ""}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {listQuery.isLoading ? (
          <div className="helper">Loading strategy board...</div>
        ) : !run ? (
          <div className="surface-empty">
            <strong>No strategy output yet</strong>
            <div className="helper">Run a training pass first. The leaderboard and diagnostics will appear here.</div>
          </div>
        ) : (
          <>
            <div style={{ marginTop: 16 }}>
              <VirtualTable
                rows={items}
                rowKey={(item) => item.symbol}
                height={560}
                rowHeight={52}
                columns={[
                  { key: "rank", header: "Rank", width: 72, align: "right", cell: (item) => item.rank },
                  {
                    key: "symbol",
                    header: "Stock",
                    width: "1.3fr",
                    cell: (item) => (
                      <Link href={`/stock/${encodeURIComponent(item.symbol)}`} className="subtle-link">
                        {item.symbol} {item.name}
                      </Link>
                    ),
                  },
                  { key: "market", header: "Market", width: 96, cell: (item) => item.market },
                  { key: "sector", header: "Sector", width: "1fr", cell: (item) => item.sector || "--" },
                  {
                    key: "score",
                    header: "Score",
                    width: 100,
                    align: "right",
                    cell: (item) => formatNullableNumber(item.score, 1),
                  },
                  {
                    key: "expected_return",
                    header: "Expected",
                    width: 116,
                    align: "right",
                    cell: (item) =>
                      item.expected_return !== null && item.expected_return !== undefined
                        ? formatPercent(item.expected_return, 2)
                        : "--",
                  },
                  {
                    key: "signal",
                    header: "Signal",
                    width: 120,
                    cell: (item) => (
                      <span className="strategy-pill" data-tone={signalTone(item.signal)}>
                        {signalLabel(item.signal)}
                      </span>
                    ),
                  },
                  {
                    key: "summary",
                    header: "Summary",
                    width: "1.6fr",
                    cell: (item) => buildStrategySignalExplanation(item),
                  },
                ]}
              />
            </div>

            <div className="stock-pagination">
              <div className="helper">{`${total} rows | page ${page}/${totalPages}`}</div>
              <div className="stock-pagination-actions">
                <button
                  type="button"
                  className="stock-page-button"
                  disabled={page <= 1}
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                >
                  Prev
                </button>
                <button
                  type="button"
                  className="stock-page-button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      <section className="card">
        <div className="page-header">
          <div>
            <h2 className="section-title" style={{ marginBottom: 4 }}>
              Backtest Confidence
            </h2>
            <p className="helper">
              Review 20d and 60d bucket behavior, spread return, win rate, and drawdown on the latest model run.
            </p>
          </div>
        </div>
        <DeferredSection
          resetKey={market || "all"}
          placeholder={<div className="helper">Backtest panel will load when this section is in view.</div>}
        >
          <SmokeButtBacktestPanel market={market} />
        </DeferredSection>
      </section>
    </div>
  );
}
