import React from "react";

import { PortfolioAnalysisPanel } from "../PortfolioAnalysisPanel";
import { PerformanceComparisonPanel } from "../PerformanceComparisonPanel";
import { StatsDashboard } from "../StatsDashboard";
import { UseStatsTargetsResult } from "../../hooks/useStatsTargets";

import styles from "./StatsPageView.module.css";

export type StatsViewTab = "portfolio" | "performance" | "events" | "news";
export type PortfolioViewTab = "watch" | "bought";
export type StatsTargetTab = "watch" | "bought";

type StatsPageViewProps = {
  authLoading: boolean;
  authed: boolean;
  symbol: string;
  start: string;
  end: string;
  statsViewTab: StatsViewTab;
  portfolioViewTab: PortfolioViewTab;
  statsTargetTab: StatsTargetTab;
  filteredStatsSymbols: string[];
  targets: UseStatsTargetsResult;
  onSymbolChange: (value: string) => void;
  onStartChange: (value: string) => void;
  onEndChange: (value: string) => void;
  onStatsViewTabChange: (value: StatsViewTab) => void;
  onPortfolioViewTabChange: (value: PortfolioViewTab) => void;
  onStatsTargetTabChange: (value: StatsTargetTab) => void;
  onSelectWatchTarget: (target: string) => void;
};

function LoadingState() {
  return (
    <div className="page">
      <section className="card market-panel">
        <div className="skeleton-stack">
          <span className="skeleton-line" data-width="short" />
          <span className="skeleton-line" data-width="long" />
          <div className="skeleton-card" />
        </div>
      </section>
    </div>
  );
}

function EmptyAccessState() {
  return (
    <div className="page">
      <section className="card market-panel">
        <div className="surface-empty">
          <strong>账户统计面板</strong>
          <div className="helper">请先登录后查看自选、持仓、收益对比与事件/新闻统计。</div>
        </div>
      </section>
    </div>
  );
}

export function StatsPageView({
  authLoading,
  authed,
  symbol,
  start,
  end,
  statsViewTab,
  portfolioViewTab,
  statsTargetTab,
  filteredStatsSymbols,
  targets,
  onSymbolChange,
  onStartChange,
  onEndChange,
  onStatsViewTabChange,
  onPortfolioViewTabChange,
  onStatsTargetTabChange,
  onSelectWatchTarget,
}: StatsPageViewProps) {
  if (authLoading) {
    return <LoadingState />;
  }

  if (!authed) {
    return <EmptyAccessState />;
  }

  const focusLabel = symbol || "全部组合";

  return (
    <div className="page">
      <section className={`card market-panel ${styles.hero}`}>
        <div className={styles.heroLead}>
          <div className={styles.heroText}>
            <span className="kicker">Portfolio Lab</span>
            <h1 className="page-title">账户统计面板</h1>
            <p className={styles.heroDescription}>
              把自选、持仓、组合收益、事件与新闻统计放在同一张工作台里，筛选状态和移动端交互也统一下来。
            </p>
          </div>
        </div>
        <div className={styles.heroMetrics}>
          <div className={styles.heroMetric}>
            <div className={styles.heroMetricLabel}>观察标的</div>
            <div className={styles.heroMetricValue}>{targets.watchTargets.length}</div>
            <div className={styles.heroMetricHelper}>{`${targets.selectedWatchSymbols.length} 个已选中`}</div>
          </div>
          <div className={styles.heroMetric}>
            <div className={styles.heroMetricLabel}>已买标的</div>
            <div className={styles.heroMetricValue}>{targets.boughtTargets.length}</div>
            <div className={styles.heroMetricHelper}>收益比较与组合分析共用同一持仓源</div>
          </div>
          <div className={styles.heroMetric}>
            <div className={styles.heroMetricLabel}>当前聚焦</div>
            <div className={styles.heroMetricValue}>{focusLabel}</div>
            <div className={styles.heroMetricHelper}>事件和新闻统计跟随当前筛选</div>
          </div>
        </div>
      </section>

      <section className={styles.sectionStack}>
        <div className={styles.targetsGrid}>
          <div className="card market-panel">
            <div className={styles.panelHeader}>
              <div className={styles.panelHeaderText}>
                <div className="card-title">观察标的</div>
                <div className="helper">支持批量勾选、快速加入和一键转为持仓。</div>
              </div>
              <span className="kicker">Watchlist</span>
            </div>

            <div className={styles.toolbarStack}>
              <div className="toolbar">
                <input
                  className="input"
                  type="text"
                  value={targets.watchInput}
                  onChange={(event) => targets.setWatchInput(event.target.value)}
                  placeholder="输入标的代码后加入观察列表"
                />
                <button type="button" className="primary-button" onClick={targets.handleQuickAddWatchTarget}>
                  加入观察
                </button>
              </div>

              <div className="toolbar">
                <button type="button" className="stock-page-button" onClick={targets.handleToggleSelectAllWatch}>
                  {targets.selectedWatchSymbols.length === targets.watchTargets.length && targets.watchTargets.length > 0
                    ? "取消全选"
                    : "全选"}
                </button>
                <button
                  type="button"
                  className="stock-page-button"
                  onClick={targets.handleBatchRemoveSelectedWatch}
                  disabled={targets.selectedWatchSymbols.length === 0}
                >
                  {`删除选中（${targets.selectedWatchSymbols.length}）`}
                </button>
                <button
                  type="button"
                  className="primary-button"
                  onClick={targets.handleAddSelectedToBought}
                  disabled={targets.selectedWatchSymbols.length === 0}
                >
                  {`转入持仓（${targets.selectedWatchSymbols.length}）`}
                </button>
              </div>
            </div>

            {targets.watchError ? (
              <div className="helper" style={{ color: "var(--finance-rise)", marginTop: 10 }}>
                {targets.watchError}
              </div>
            ) : null}

            {targets.watchTargets.length === 0 ? (
              <div className="surface-empty" style={{ marginTop: 14 }}>
                <strong>暂无观察标的</strong>
                <div className="helper">可以在个股页添加，也可以直接在这里手动维护。</div>
              </div>
            ) : (
              <div className={styles.list} style={{ marginTop: 14 }}>
                {targets.watchTargets.map((item) => (
                  <div key={item} className={styles.listItem}>
                    <label className={styles.watchLabel}>
                      <input
                        type="checkbox"
                        checked={targets.selectedWatchSymbols.includes(item)}
                        onChange={() => targets.handleToggleWatchSelection(item)}
                      />
                      <span>{item}</span>
                    </label>
                    <div className={styles.itemActions}>
                      <button type="button" className="stock-page-button" onClick={() => onSelectWatchTarget(item)}>
                        定位
                      </button>
                      <button
                        type="button"
                        className="stock-page-button"
                        onClick={() => targets.handleAddSingleToBought(item)}
                      >
                        转入持仓
                      </button>
                      <button
                        type="button"
                        className="stock-page-button"
                        onClick={() => targets.handleRemoveWatchTarget(item)}
                      >
                        删除
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="card market-panel" data-tone="warm">
            <div className={styles.panelHeader}>
              <div className={styles.panelHeaderText}>
                <div className="card-title">已买标的</div>
                <div className="helper">持仓信息将直接驱动收益对比和组合分析。</div>
              </div>
              <span className="kicker">Positions</span>
            </div>
            {targets.boughtTargets.length === 0 ? (
              <div className="surface-empty">
                <strong>暂无持仓记录</strong>
                <div className="helper">从左侧观察列表直接转入，或在个股页补充买入记录。</div>
              </div>
            ) : (
              <div className={styles.list}>
                {targets.boughtTargets.map((item) => (
                  <div key={item.symbol} className={styles.listItem}>
                    <div className={styles.itemMeta}>
                      <strong>{item.symbol}</strong>
                      <div className="helper">{`买入价 ${item.buyPrice} · ${item.lots} 手 · ${item.buyDate}`}</div>
                      <div className="helper">{`手续费 ${item.fee}${item.note ? ` · ${item.note}` : ""}`}</div>
                    </div>
                    <div className={styles.itemActions}>
                      <button type="button" className="stock-page-button" onClick={() => targets.openBuyModal(item.symbol)}>
                        编辑
                      </button>
                      <button
                        type="button"
                        className="stock-page-button"
                        onClick={() => targets.handleRemoveBoughtTarget(item.symbol)}
                      >
                        删除持仓
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className={`toolbar sticky-filter-bar ${styles.tabBar}`}>
          <button
            type="button"
            className="stock-page-button"
            data-active={statsViewTab === "portfolio"}
            onClick={() => onStatsViewTabChange("portfolio")}
          >
            组合分析
          </button>
          <button
            type="button"
            className="stock-page-button"
            data-active={statsViewTab === "performance"}
            onClick={() => onStatsViewTabChange("performance")}
          >
            收益对比
          </button>
          <button
            type="button"
            className="stock-page-button"
            data-active={statsViewTab === "events"}
            onClick={() => onStatsViewTabChange("events")}
          >
            事件统计
          </button>
          <button
            type="button"
            className="stock-page-button"
            data-active={statsViewTab === "news"}
            onClick={() => onStatsViewTabChange("news")}
          >
            新闻统计
          </button>
        </div>

        {statsViewTab === "portfolio" ? (
          <div className={styles.sectionStack}>
            <div className={`toolbar ${styles.filterBar}`}>
              <button
                type="button"
                className="stock-page-button"
                data-active={portfolioViewTab === "watch"}
                onClick={() => onPortfolioViewTabChange("watch")}
              >
                观察标的
              </button>
              <button
                type="button"
                className="stock-page-button"
                data-active={portfolioViewTab === "bought"}
                onClick={() => onPortfolioViewTabChange("bought")}
              >
                已买标的
              </button>
            </div>
            <PortfolioAnalysisPanel
              symbols={portfolioViewTab === "watch" ? targets.watchTargets : targets.boughtTargets.map((item) => item.symbol)}
              title={portfolioViewTab === "watch" ? "观察标的行业暴露与组合分析" : "已买标的行业暴露与组合分析"}
              emptyText={portfolioViewTab === "watch" ? "先添加观察标的后再查看分析。" : "先记录持仓后再查看分析。"}
              pageSize={10}
            />
          </div>
        ) : null}

        {statsViewTab === "performance" ? (
          <PerformanceComparisonPanel watchSymbols={targets.watchTargets} boughtTargets={targets.boughtTargets} />
        ) : null}

        {statsViewTab === "events" || statsViewTab === "news" ? (
          <div className={styles.sectionStack}>
            <div className={`toolbar ${styles.filterBar}`}>
              <button
                type="button"
                className="stock-page-button"
                data-active={statsTargetTab === "watch"}
                onClick={() => onStatsTargetTabChange("watch")}
              >
                观察标的
              </button>
              <button
                type="button"
                className="stock-page-button"
                data-active={statsTargetTab === "bought"}
                onClick={() => onStatsTargetTabChange("bought")}
              >
                已买标的
              </button>
            </div>

            <div className={`toolbar sticky-filter-bar ${styles.stickyBar}`}>
              <label className={styles.filterField}>
                <span className={styles.filterLabel}>筛选标的</span>
                <input
                  className="input"
                  type="text"
                  value={symbol}
                  onChange={(event) => onSymbolChange(event.target.value.trim().toUpperCase())}
                  placeholder="可选，精确筛选单个标的"
                />
              </label>
              <label className={styles.filterField}>
                <span className={styles.filterLabel}>开始日期</span>
                <input className="input" type="date" value={start} onChange={(event) => onStartChange(event.target.value)} />
              </label>
              <label className={styles.filterField}>
                <span className={styles.filterLabel}>结束日期</span>
                <input className="input" type="date" value={end} onChange={(event) => onEndChange(event.target.value)} />
              </label>
            </div>

            {filteredStatsSymbols.length === 0 ? (
              <div className="surface-empty">
                <strong>{statsTargetTab === "watch" ? "暂无观察标的" : "暂无持仓标的"}</strong>
                <div className="helper">
                  {statsTargetTab === "watch" ? "先添加观察标的后再查看统计。" : "先录入持仓后再查看统计。"}
                </div>
              </div>
            ) : (
              <StatsDashboard
                symbols={filteredStatsSymbols}
                start={start || undefined}
                end={end || undefined}
                view={statsViewTab === "events" ? "events" : "news"}
              />
            )}
          </div>
        ) : null}
      </section>

      {targets.buyModalOpen ? (
        <div className="stats-modal-mask">
          <div className="stats-modal-card market-panel">
            <div className={styles.modalTitle}>
              <h3 style={{ margin: 0 }}>{`持仓设置 · ${targets.buyForm.symbol}`}</h3>
              <div className="helper">
                {targets.pendingBuySymbols.length > 0
                  ? `当前保存后还会继续处理 ${targets.pendingBuySymbols.length} 个标的。`
                  : "买入价格、手数和日期会同步驱动组合收益计算。"}
              </div>
            </div>

            <form onSubmit={targets.handleSaveBoughtTarget} onKeyDown={targets.handleBuyFormKeyDown} className={styles.modalForm}>
              <input className="input" type="text" value={targets.buyForm.symbol} readOnly />
              <input
                className="input"
                type="number"
                min="0"
                step="0.0001"
                value={targets.buyForm.buyPrice}
                onChange={(event) => targets.setBuyForm((prev) => ({ ...prev, buyPrice: event.target.value }))}
                placeholder="买入价格"
                required
              />
              <input
                className="input"
                type="number"
                min="0"
                step="0.01"
                value={targets.buyForm.lots}
                onChange={(event) => targets.setBuyForm((prev) => ({ ...prev, lots: event.target.value }))}
                placeholder="买入手数"
                required
              />
              <input
                className="input"
                type="date"
                value={targets.buyForm.buyDate}
                onChange={(event) => targets.setBuyForm((prev) => ({ ...prev, buyDate: event.target.value }))}
                required
              />
              <input
                className="input"
                type="number"
                min="0"
                step="0.01"
                value={targets.buyForm.fee}
                onChange={(event) => targets.setBuyForm((prev) => ({ ...prev, fee: event.target.value }))}
                placeholder="手续费"
              />
              <input
                className="input"
                type="text"
                value={targets.buyForm.note}
                onChange={(event) => targets.setBuyForm((prev) => ({ ...prev, note: event.target.value }))}
                placeholder="备注（可选）"
              />
              {targets.buyModalError ? (
                <div className="helper" style={{ color: "var(--finance-rise)" }}>
                  {targets.buyModalError}
                </div>
              ) : null}
              <div className={styles.modalActions}>
                <button type="button" className="stock-page-button" onClick={targets.handleCancelBuyModal}>
                  取消
                </button>
                <button type="submit" className="primary-button">
                  保存
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </div>
  );
}
