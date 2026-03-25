import Link from "next/link";
import React, { useMemo, useState } from "react";

import { useApiQuery } from "../../hooks/useApiQuery";
import {
  getSmokeButtStrategyLeaderboard,
  SmokeButtListResponse,
  StrategySignal,
  trainSmokeButtStrategy,
} from "../../services/api";
import { formatNullableNumber, formatPercent } from "../../utils/format";

const PAGE_SIZE = 20;

const SIGNAL_OPTIONS: Array<{ value: "" | StrategySignal; label: string }> = [
  { value: "", label: "全部信号" },
  { value: "strong_buy", label: "强关注" },
  { value: "buy", label: "关注" },
  { value: "watch", label: "观察" },
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

export default function SmokeButtStrategyPage() {
  const [market, setMarket] = useState<"" | "A" | "HK" | "US">("");
  const [signal, setSignal] = useState<"" | StrategySignal>("");
  const [page, setPage] = useState(1);
  const [isTraining, setIsTraining] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const offset = useMemo(() => (page - 1) * PAGE_SIZE, [page]);
  const listQuery = useApiQuery<SmokeButtListResponse>(
    ["smoke-butt-board", market || "all", signal || "all", page],
    () =>
      getSmokeButtStrategyLeaderboard(
        {
          market: market || undefined,
          signal: signal || undefined,
          limit: PAGE_SIZE,
          offset,
        },
        { cache: false },
      ),
    {
      staleTimeMs: 2 * 60 * 1000,
      cacheTimeMs: 10 * 60 * 1000,
      retry: 1,
    },
  );

  const run = listQuery.data?.run ?? null;
  const items = listQuery.data?.items ?? [];
  const total = listQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const handleTrain = async () => {
    setIsTraining(true);
    setNotice(null);
    try {
      const response = await trainSmokeButtStrategy({
        force_retrain: true,
        time_limit_seconds: 120,
      });
      setNotice(`训练完成：${response.run.as_of} · 样本 ${response.run.train_rows} · 覆盖 ${response.run.scored_rows}`);
      await listQuery.refetch(() =>
        getSmokeButtStrategyLeaderboard(
          {
            market: market || undefined,
            signal: signal || undefined,
            limit: PAGE_SIZE,
            offset: 0,
          },
          { cache: false },
        ),
      );
      setPage(1);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "训练失败");
    } finally {
      setIsTraining(false);
    }
  };

  return (
    <div className="page">
      <section className="card hero-card">
        <div className="page-header">
          <div>
            <h1 className="page-title">AutoGluon 烟蒂股策略</h1>
            <p className="helper">
              用 AutoGluon 对历史价格、财务、事件、回购和研报做横截面排序，输出当前的烟蒂股候选榜单。
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
            <div className="card-title">策略状态</div>
            <div className="hero-metric-value">{run ? "Ready" : "Not Trained"}</div>
            <div className="helper">{run ? `最近训练：${run.as_of}` : "还没有训练结果"}</div>
          </div>
          <div className="hero-metric">
            <div className="card-title">训练样本</div>
            <div className="hero-metric-value">{run ? formatNullableNumber(run.train_rows, 0) : "--"}</div>
            <div className="helper">用于 AutoGluon 拟合的历史样本数</div>
          </div>
          <div className="hero-metric">
            <div className="card-title">覆盖股票</div>
            <div className="hero-metric-value">{run ? formatNullableNumber(run.scored_rows, 0) : "--"}</div>
            <div className="helper">最新一轮成功输出的策略评分数量</div>
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
            <option value="A">A 股</option>
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
              训练时间：{new Date(run.trained_at).toLocaleString("zh-CN")} · 预测窗口：{run.label_horizon} 个交易日
            </div>
            <div className="strategy-pill-row">
              {run.feature_importance.slice(0, 5).map((item) => (
                <span key={item.feature} className="strategy-pill" data-tone="neutral">
                  {item.feature}
                  {item.importance !== null && item.importance !== undefined ? ` · ${formatNullableNumber(item.importance, 2)}` : ""}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {listQuery.isLoading ? (
          <div className="helper">策略榜单加载中...</div>
        ) : !run ? (
          <div className="surface-empty">
            <strong>还没有策略结果</strong>
            <div className="helper">先点击上面的“重新训练”，完成后这里会出现榜单和特征重要性。</div>
          </div>
        ) : (
          <>
            <div style={{ overflowX: "auto", marginTop: 16 }}>
              <table className="data-table dense-table">
                <thead>
                  <tr>
                    <th>排名</th>
                    <th>股票</th>
                    <th>市场</th>
                    <th>行业</th>
                    <th>策略分</th>
                    <th>预期收益</th>
                    <th>信号</th>
                    <th>摘要</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.symbol}>
                      <td>{item.rank}</td>
                      <td>
                        <Link href={`/stock/${encodeURIComponent(item.symbol)}`} className="subtle-link">
                          {item.symbol} {item.name}
                        </Link>
                      </td>
                      <td>{item.market}</td>
                      <td>{item.sector}</td>
                      <td>{formatNullableNumber(item.score, 1)}</td>
                      <td>{item.expected_return !== null && item.expected_return !== undefined ? formatPercent(item.expected_return, 2) : "--"}</td>
                      <td>
                        <span className="strategy-pill" data-tone={signalTone(item.signal)}>
                          {signalLabel(item.signal)}
                        </span>
                      </td>
                      <td>{item.summary ?? "--"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="stock-pagination">
              <div className="helper">
                共 {total} 条，当前第 {page}/{totalPages} 页
              </div>
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
    </div>
  );
}
