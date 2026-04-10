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
    loading: () => <div className="helper">准备回测面板...</div>,
  },
);

const SIGNAL_OPTIONS: Array<{ value: "" | StrategySignal; label: string }> = [
  { value: "", label: "全部信号" },
  { value: "strong_buy", label: "强烈买入" },
  { value: "buy", label: "买入" },
  { value: "watch", label: "观望" },
  { value: "avoid", label: "回避" },
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
            <h1 className="page-title">AutoGluon 烟头策略</h1>
            <p className="helper">
              历史价格、基本面、事件、回购和研报等数据被整合为跨截面选股看板。
            </p>
          </div>
          <div className="toolbar">
            <button type="button" className="primary-button" onClick={() => void handleTrain()} disabled={isTraining}>
              {isTraining ? "训练中..." : "重新训练"}
            </button>
          </div>
        </div>
        <div className="hero-grid">
          <div className="hero-metric">
            <div className="card-title">状态</div>
            <div className="hero-metric-value">{run ? "就绪" : "未训练"}</div>
            <div className="helper">{run ? `最新运行：${run.as_of}` : "运行模型以生成看板。"}</div>
          </div>
          <div className="hero-metric">
            <div className="card-title">训练行数</div>
            <div className="hero-metric-value">{run ? formatNullableNumber(run.train_rows, 0) : "--"}</div>
            <div className="helper">用于模型拟合的行数</div>
          </div>
          <div className="hero-metric">
            <div className="card-title">已评分标的</div>
            <div className="hero-metric-value">{run ? formatNullableNumber(run.scored_rows, 0) : "--"}</div>
            <div className="helper">带有新信号的标的数量</div>
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
            <option value="">全部市场</option>
            <option value="A">A股</option>
            <option value="HK">港股</option>
            <option value="US">美股</option>
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
              {`训练于 ${new Date(run.trained_at).toLocaleString("zh-CN")} | 持有周期 ${run.label_horizon} 个交易日`}
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
          <div className="helper">策略看板加载中...</div>
        ) : !run ? (
          <div className="surface-empty">
            <strong>暂无策略输出</strong>
            <div className="helper">请先运行一次训练。排行榜和诊断信息将在此显示。</div>
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
                  { key: "rank", header: "排名", width: 72, align: "right", cell: (item) => item.rank },
                  {
                    key: "symbol",
                    header: "股票",
                    width: "1.3fr",
                    cell: (item) => (
                      <Link href={`/stock/${encodeURIComponent(item.symbol)}`} className="subtle-link">
                        {item.symbol} {item.name}
                      </Link>
                    ),
                  },
                  { key: "market", header: "市场", width: 96, cell: (item) => item.market },
                  { key: "sector", header: "板块", width: "1fr", cell: (item) => item.sector || "--" },
                  {
                    key: "score",
                    header: "得分",
                    width: 100,
                    align: "right",
                    cell: (item) => formatNullableNumber(item.score, 1),
                  },
                  {
                    key: "expected_return",
                    header: "预期收益",
                    width: 116,
                    align: "right",
                    cell: (item) =>
                      item.expected_return !== null && item.expected_return !== undefined
                        ? formatPercent(item.expected_return, 2)
                        : "--",
                  },
                  {
                    key: "signal",
                    header: "信号",
                    width: 120,
                    cell: (item) => (
                      <span className="strategy-pill" data-tone={signalTone(item.signal)}>
                        {signalLabel(item.signal)}
                      </span>
                    ),
                  },
                  {
                    key: "summary",
                    header: "摘要",
                    width: "1.6fr",
                    cell: (item) => buildStrategySignalExplanation(item),
                  },
                ]}
              />
            </div>

            <div className="stock-pagination">
              <div className="helper">{`${total} 行 | 第 ${page}/${totalPages} 页`}</div>
              <div className="stock-pagination-actions">
                <button
                  type="button"
                  className="stock-page-button"
                  disabled={page <= 1}
                  onClick={() => setPage((value) => Math.max(1, value - 1))}
                >
                  上一页
                </button>
                <button
                  type="button"
                  className="stock-page-button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
                >
                  下一页
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
              回测置信度
            </h2>
            <p className="helper">
              查看最新模型运行的 20 日和 60 日分组表现、利差收益、胜率和回撤。
            </p>
          </div>
        </div>
        <DeferredSection
          resetKey={market || "all"}
          placeholder={<div className="helper">回测面板将在滚动到此处时加载。</div>}
        >
          <SmokeButtBacktestPanel market={market} />
        </DeferredSection>
      </section>
    </div>
  );
}
