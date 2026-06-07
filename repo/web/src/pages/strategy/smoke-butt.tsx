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
import {
  buildCigarbuttQueryKey,
  loadCigarbuttAnalysis,
} from "../../domain/strategyScore";

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
  const [activeStrategy, setActiveStrategy] = useState<"autogluon" | "cigarbutt">("autogluon");
  const [market, setMarket] = useState<"" | "A" | "HK" | "US">("");
  const [signal, setSignal] = useState<"" | StrategySignal>("");
  const [page, setPage] = useState(1);
  const [isTraining, setIsTraining] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [cigarbuttSymbol, setCigarbuttSymbol] = useState("");
  const [cigarbuttQuery, setCigarbuttQuery] = useState<readonly string[] | null>(null);
  const cigarbuttResult = useApiQuery<{
    symbol: string;
    stock_price?: number | null;
    analysis: Record<string, unknown>;
  }>(
    cigarbuttQuery,
    () => (cigarbuttQuery ? loadCigarbuttAnalysis(cigarbuttQuery[1]) : Promise.resolve({ symbol: "", analysis: {} })),
    { staleTimeMs: 0, cacheTimeMs: 0, retry: 0, label: "cigarbutt-analysis" },
  );

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
            <h1 className="page-title">策略中心</h1>
            <p className="helper">
              切换不同策略模型查看分析结果。
            </p>
          </div>
          <div className="toolbar">
            <button
              type="button"
              className={activeStrategy === "autogluon" ? "primary-button" : "input"}
              onClick={() => setActiveStrategy("autogluon")}
            >
              AutoGluon 烟蒂股
            </button>
            <button
              type="button"
              className={activeStrategy === "cigarbutt" ? "primary-button" : "input"}
              onClick={() => setActiveStrategy("cigarbutt")}
            >
              静态价值型烟蒂股
            </button>
          </div>
        </div>
        {activeStrategy === "autogluon" ? (
        <>
        <div className="page-header" style={{ marginTop: 12 }}>
          <div>
            <h2 className="page-title" style={{ fontSize: 18 }}>AutoGluon 烟头策略</h2>
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
        </>
        ) : (
        <div style={{ marginTop: 12 }}>
          <h2 className="page-title" style={{ fontSize: 18 }}>静态价值型烟蒂股分析</h2>
          <p className="helper">基于 T0/T1/T2 三层 NAV、子类型分析、22 项 Fact Check 和交易计划的深度价值筛选。</p>
          <form
            className="toolbar"
            style={{ marginTop: 12 }}
            onSubmit={(e) => {
              e.preventDefault();
              const s = cigarbuttSymbol.trim().toUpperCase();
              if (s) setCigarbuttQuery(buildCigarbuttQueryKey(s));
            }}
          >
            <input
              className="input"
              type="text"
              value={cigarbuttSymbol}
              onChange={(e) => setCigarbuttSymbol(e.target.value)}
              placeholder="输入股票代码，例如 600000、0700.HK"
            />
            <button type="submit" className="primary-button">
              分析
            </button>
          </form>
          {cigarbuttResult.isLoading && <div className="helper">分析中...</div>}
          {cigarbuttResult.error && (
            <div className="helper">分析失败：{cigarbuttResult.error.message}</div>
          )}
          {cigarbuttResult.data?.analysis && (
            <CigarbuttResultPanel data={cigarbuttResult.data} />
          )}
        </div>
        )}
      </section>

      {activeStrategy === "autogluon" && (
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
      )}

      {activeStrategy === "autogluon" && (
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
      )}
    </div>
  );
}

function CigarbuttResultPanel({
  data,
}: {
  data: { symbol: string; stock_price?: number | null; analysis: Record<string, unknown> };
}) {
  const a = data.analysis as Record<string, unknown>;

  const fmtNum = (v: unknown, digits = 2) =>
    typeof v === "number" ? v.toFixed(digits) : v === null || v === undefined ? "--" : String(v);
  const fmtPrice = (v: unknown) => fmtNum(v, 3);
  const fmtPct = (v: unknown) =>
    typeof v === "number" ? `${(v * 100).toFixed(1)}%` : "--";

  const subtypeA = (a.subtype_a as Record<string, unknown>) || {};
  const subtypeB = (a.subtype_b as Record<string, unknown>) || {};
  const subtypeC = (a.subtype_c as Record<string, unknown>) || {};
  const redemption = (a.redemption_path as Record<string, unknown>) || {};
  const tradePlan = (a.trade_plan as Record<string, unknown>) || {};
  const entry = (tradePlan.entry as Record<string, unknown>) || {};
  const stopLoss = (tradePlan.stop_loss as Record<string, unknown>) || {};
  const takeProfit = (tradePlan.take_profit as Record<string, unknown>) || {};
  const riskFlags = (a.risk_flags as string[]) || [];

  const ratingTone = (r: unknown): "positive" | "negative" | "neutral" => {
    if (typeof r !== "string") return "neutral";
    if (r.includes("A") || r.includes("强") || r.includes("优")) return "positive";
    if (r.includes("C") || r.includes("弱") || r.includes("D") || r.includes("差")) return "negative";
    return "neutral";
  };

  const PassBadge = ({ pass }: { pass: boolean }) => (
    <span
      className="strategy-pill"
      data-tone={pass ? "positive" : "negative"}
      style={{ fontSize: 11, padding: "4px 10px" }}
    >
      {pass ? "✓ 通过" : "✗ 未通过"}
    </span>
  );

  const navCards = [
    {
      label: "T0 清算价值",
      nav: a.t0_nav_per_share,
      ratio: a.t0_ratio,
      pass: !!a.is_t0_pass,
      desc: "最保守：现金 + 应收 + 存货折扣",
    },
    {
      label: "T1 营运资本",
      nav: a.t1_nav_per_share,
      ratio: a.t1_ratio,
      pass: !!a.is_t1_pass,
      desc: "较保守：T0 + 营运资产",
    },
    {
      label: "T2 账面价值",
      nav: a.t2_nav_per_share,
      ratio: a.t2_ratio,
      pass: !!a.is_t2_pass,
      desc: "最宽松：全部净资产",
    },
  ];

  const fcTone = ratingTone(a.fact_check_rating);
  const bonusTone = ratingTone(a.bonus_adjusted_rating);

  return (
    <div>
      {/* 顶部概览 */}
      <div className="hero-grid" style={{ marginTop: 16 }}>
        <div className="hero-metric">
          <div className="helper">股票代码</div>
          <div className="hero-metric-value">{data.symbol}</div>
          <div className="helper">当前股价 {fmtPrice(data.stock_price)}</div>
        </div>
        <div className="hero-metric">
          <div className="helper">最佳 T 级</div>
          <div className="hero-metric-value">{String(a.best_t_level ?? "--")}</div>
          <div className="helper">安全边际分层</div>
        </div>
        <div className="hero-metric">
          <div className="helper">Fact Check 评级</div>
          <div
            className="hero-metric-value"
            style={{
              color:
                fcTone === "positive"
                  ? "#b42318"
                  : fcTone === "negative"
                  ? "#027a48"
                  : "#1d4ed8",
            }}
          >
            {String(a.fact_check_rating ?? "--")}
          </div>
          <div className="helper">22 项事实核查综合评级</div>
        </div>
        <div className="hero-metric">
          <div className="helper">加分后评级</div>
          <div
            className="hero-metric-value"
            style={{
              color:
                bonusTone === "positive"
                  ? "#b42318"
                  : bonusTone === "negative"
                  ? "#027a48"
                  : "#1d4ed8",
            }}
          >
            {String(a.bonus_adjusted_rating ?? "--")}
          </div>
          <div className="helper">国企 / 上市子公司加分后</div>
        </div>
      </div>

      {/* NAV 安全边际 */}
      <div className="summary-grid" style={{ marginTop: 18 }}>
        {navCards.map((t) => (
          <div
            key={t.label}
            className="summary-card"
            style={{ borderLeft: `4px solid ${t.pass ? "#10b981" : "#ef4444"}` }}
          >
            <div
              className="card-title"
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 8,
              }}
            >
              {t.label}
              <PassBadge pass={t.pass} />
            </div>
            <div
              style={{
                marginTop: 12,
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 12,
              }}
            >
              <div>
                <div className="helper">NAV / 股</div>
                <div className="metric-value">{fmtPrice(t.nav)}</div>
              </div>
              <div>
                <div className="helper">股价 / NAV</div>
                <div className="metric-value">{fmtNum(t.ratio)}</div>
              </div>
            </div>
            <div className="helper" style={{ marginTop: 8, fontSize: 11 }}>
              {t.desc}
            </div>
          </div>
        ))}
      </div>

      {/* 子类型 & 兑现路径 */}
      <div className="card" style={{ marginTop: 18 }}>
        <div className="card-title">子类型识别 & 兑现路径</div>
        <div className="strategy-pill-row">
          <span
            className="strategy-pill"
            data-tone={subtypeA.is_valid ? "positive" : "neutral"}
          >
            {subtypeA.is_valid ? "✓" : "○"} 子类型A：高股息破净
          </span>
          <span
            className="strategy-pill"
            data-tone={subtypeB.is_valid ? "positive" : "neutral"}
          >
            {subtypeB.is_valid ? "✓" : "○"} 子类型B：控股套利
          </span>
          <span
            className="strategy-pill"
            data-tone={(subtypeC.subtype as string) ? "positive" : "neutral"}
          >
            {((subtypeC.subtype as string) || "--") !== "--" ? "✓" : "○"} 子类型C：
            {(subtypeC.subtype as string) || "无事件驱动"}
          </span>
          <span
            className="strategy-pill"
            data-tone={redemption.has_valid_path ? "positive" : "negative"}
          >
            {redemption.has_valid_path ? "✓ 有" : "✗ 无"} 兑现路径
          </span>
        </div>
      </div>

      {/* Fact Check & 加分 */}
      <div className="card" style={{ marginTop: 18 }}>
        <div className="card-title">Fact Check & 质量加分</div>
        <div className="metric-grid compact-grid" style={{ marginTop: 12 }}>
          {[
            {
              label: "Fact Check 评级",
              value: a.fact_check_rating,
              tone: fcTone,
            },
            { label: "国企加分", value: a.state_owned_bonus, tone: "neutral" },
            {
              label: "上市子公司加分",
              value: a.listed_subsidiary_bonus,
              tone: "neutral",
            },
            { label: "总加分", value: a.total_bonus, tone: "neutral" },
          ].map((item) => (
            <div key={item.label} className="metric-card">
              <div className="helper">{item.label}</div>
              <div
                className="metric-value"
                style={{
                  color:
                    item.tone === "positive"
                      ? "#b42318"
                      : item.tone === "negative"
                      ? "#027a48"
                      : undefined,
                }}
              >
                {typeof item.value === "number"
                  ? item.value.toFixed(1)
                  : String(item.value ?? "--")}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 交易计划 */}
      <div className="card" style={{ marginTop: 18 }}>
        <div className="card-title">交易计划</div>
        <div className="summary-grid" style={{ marginTop: 12 }}>
          <div
            className="summary-card"
            style={{ borderLeft: "4px solid #3b82f6" }}
          >
            <div className="card-title" style={{ fontSize: 13 }}>
              建仓计划
            </div>
            <div
              style={{
                marginTop: 10,
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <div className="helper">
                目标仓位{" "}
                <strong>{fmtPct(entry.target_position_ratio)}</strong>
              </div>
              <div className="helper">
                首次买入价{" "}
                <strong style={{ color: "#0f172a" }}>
                  {fmtPrice(entry.entry_price)}
                </strong>
              </div>
              <div className="helper">
                跌 10% 追加{" "}
                <strong style={{ color: "#0f172a" }}>
                  {fmtPrice(entry.add_10pct_price)}
                </strong>
              </div>
              <div className="helper">
                跌 15% 满仓{" "}
                <strong style={{ color: "#0f172a" }}>
                  {fmtPrice(entry.add_15pct_price)}
                </strong>
              </div>
            </div>
          </div>

          <div
            className="summary-card"
            style={{ borderLeft: "4px solid #ef4444" }}
          >
            <div className="card-title" style={{ fontSize: 13 }}>
              止损计划
            </div>
            <div
              style={{
                marginTop: 10,
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <div className="helper">硬性止损价</div>
              <div className="metric-value" style={{ color: "#ef4444" }}>
                {fmtPrice(stopLoss.hard_stop_price)}
              </div>
              <div className="helper" style={{ fontSize: 11 }}>
                跌破此价无条件离场
              </div>
            </div>
          </div>

          <div
            className="summary-card"
            style={{ borderLeft: "4px solid #10b981" }}
          >
            <div className="card-title" style={{ fontSize: 13 }}>
              止盈计划
            </div>
            <div
              style={{
                marginTop: 10,
                display: "flex",
                flexDirection: "column",
                gap: 8,
              }}
            >
              <div className="helper">
                T0 目标减仓{" "}
                <strong style={{ color: "#0f172a" }}>
                  {fmtPrice(takeProfit.t0_target_price)}
                </strong>
              </div>
              <div className="helper">
                T1 目标减仓{" "}
                <strong style={{ color: "#0f172a" }}>
                  {fmtPrice(takeProfit.t1_target_price)}
                </strong>
              </div>
              <div className="helper">
                T2 清仓价{" "}
                <strong style={{ color: "#0f172a" }}>
                  {fmtPrice(takeProfit.t2_target_price)}
                </strong>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* 风险标记 */}
      {riskFlags.length > 0 && (
        <div
          className="card"
          style={{
            marginTop: 18,
            borderColor: "rgba(239, 68, 68, 0.3)",
            background: "linear-gradient(180deg, #fff5f5 0%, #ffffff 100%)",
          }}
        >
          <div
            className="card-title"
            style={{
              color: "#dc2626",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            ⚠ 风险标记
          </div>
          <ul
            style={{
              marginTop: 10,
              paddingLeft: 18,
              color: "#7f1d1d",
              lineHeight: 1.8,
            }}
          >
            {riskFlags.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
