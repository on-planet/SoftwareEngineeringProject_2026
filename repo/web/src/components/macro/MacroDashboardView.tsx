import React from "react";
import ReactECharts from "echarts-for-react";

import { MacroDashboardModel } from "../../hooks/useMacroDashboard";
import { formatLoosePercent, formatNullableNumber } from "../../utils/format";
import { VirtualTable } from "../virtual/VirtualTable";
import {
  COUNTRY_LABELS,
  formatFamilyLabel,
  formatFullValue,
  formatScore,
  formatValue,
  SortOrder,
} from "./macroUtils";

import styles from "./MacroDashboardView.module.css";

type MacroDashboardViewProps = {
  model: MacroDashboardModel;
};

type ReferenceTableCardProps = {
  title: string;
  helper: string;
  total: number;
  loading: boolean;
  error: string | null;
  emptyMessage: string;
  eyebrow?: string;
  tone?: "cool" | "warm";
  children: React.ReactNode;
};

function formatDateTime(value?: string | null) {
  if (!value) {
    return "--";
  }
  return value.replace("T", " ").slice(0, 16);
}

function ReferenceTableCard({
  title,
  helper,
  total,
  loading,
  error,
  emptyMessage,
  eyebrow,
  tone = "cool",
  children,
}: ReferenceTableCardProps) {
  return (
    <div className={`card market-panel ${styles.referenceCard}`} data-tone={tone}>
      <div className={styles.referenceCardHeader}>
        <div className={styles.referenceTitleGroup}>
          {eyebrow ? <span className={styles.referenceEyebrow}>{eyebrow}</span> : null}
          <h3 className="section-title" style={{ marginBottom: 4 }}>
            {title}
          </h3>
          <div className="helper">{helper}</div>
        </div>
        <div className="helper">{loading ? "加载中..." : `${total} 条`}</div>
      </div>
      {loading ? (
        <div className="skeleton-stack">
          <span className="skeleton-line" data-width="medium" />
          <div className="skeleton-card" />
        </div>
      ) : null}
      {!loading && error ? (
        <div className="surface-empty">
          <strong>参考面板加载失败</strong>
          <div className="helper">{error}</div>
        </div>
      ) : null}
      {!loading && !error && total === 0 ? (
        <div className="surface-empty">
          <strong>暂无数据</strong>
          <div className="helper">{emptyMessage}</div>
        </div>
      ) : null}
      {!loading && !error && total > 0 ? <div className={styles.tableWrap}>{children}</div> : null}
    </div>
  );
}

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

function ReferenceVirtualTable<T>({
  rows,
  rowKey,
  columns,
}: {
  rows: T[];
  rowKey: (row: T, index: number) => string | number;
  columns: Array<{
    key: string;
    header: React.ReactNode;
    width?: string | number;
    align?: "left" | "center" | "right";
    cell: (row: T, index: number) => React.ReactNode;
  }>;
}) {
  return <VirtualTable rows={rows} columns={columns} rowKey={rowKey} height={280} rowHeight={44} />;
}

export function MacroDashboardView({ model }: MacroDashboardViewProps) {
  const {
    loading,
    error,
    search,
    setSearch,
    country,
    setCountry,
    family,
    setFamily,
    sort,
    setSort,
    start,
    setStart,
    end,
    setEnd,
    cards,
    visibleCards,
    countryOptions,
    familyOptions,
    pagedSnapshots,
    setSnapshotPage,
    selectedKey,
    setSelectedKey,
    selectedCard,
    series,
    seriesLoading,
    chartOption,
    latestPoint,
    referencePanels,
  } = model;

  const referencePanelCount = 5;
  const referenceLoadedRows =
    referencePanels.fxSpot.total +
    referencePanels.fxSwap.total +
    referencePanels.fxPair.total +
    referencePanels.bondTrades.total +
    referencePanels.bondQuotes.total;
  const referenceReadyCount = [
    referencePanels.fxSpot,
    referencePanels.fxSwap,
    referencePanels.fxPair,
    referencePanels.bondTrades,
    referencePanels.bondQuotes,
  ].filter((panel) => !panel.loading && !panel.error && panel.total > 0).length;

  if (loading) {
    return <LoadingState />;
  }

  if (error && cards.length === 0) {
    return (
      <div className="page">
        <section className="card market-panel">
          <div className="surface-empty">
            <strong>宏观快照加载失败</strong>
            <div className="helper">{error}</div>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="page">
      <section className={`card market-panel ${styles.hero}`}>
        <div className={styles.heroLead}>
          <div>
            <span className="kicker">宏观面板</span>
            <h1 className="page-title">宏观指标看板</h1>
            <p className={styles.heroDescription}>
              世界银行与 AkShare 指标已统一整合至一个工作区，包含联动卡片、图表和参考表格。
            </p>
          </div>
        </div>
        <div className={styles.heroMetrics}>
          <div className={styles.heroMetric}>
            <div className={styles.heroMetricLabel}>指标数</div>
            <div className={styles.heroMetricValue}>{cards.length}</div>
            <div className={styles.heroMetricHelper}>快照合并后的不同键值数量</div>
          </div>
          <div className={styles.heroMetric}>
            <div className={styles.heroMetricLabel}>可见数</div>
            <div className={styles.heroMetricValue}>{visibleCards.length}</div>
            <div className={styles.heroMetricHelper}>筛选后的卡片和关联图表范围</div>
          </div>
          <div className={styles.heroMetric}>
            <div className={styles.heroMetricLabel}>已选择</div>
            <div className={styles.heroMetricValue}>{selectedCard ? selectedCard.label : "--"}</div>
            <div className={styles.heroMetricHelper}>{selectedCard ? selectedCard.countryLabel : "选择一个指标"}</div>
          </div>
        </div>
      </section>

      <section className={`toolbar sticky-filter-bar ${styles.stickyBar}`}>
        <label className={styles.filterField}>
          <span className={styles.filterLabel}>搜索</span>
          <input
            className="input"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="GDP / CPI / 就业 / 中国"
          />
        </label>
        <label className={styles.filterField}>
          <span className={styles.filterLabel}>国家/地区</span>
          <select className="select" value={country} onChange={(event) => setCountry(event.target.value)}>
            <option value="">全部</option>
            {countryOptions.map((item) => (
              <option key={item} value={item}>
                {COUNTRY_LABELS[item] || item}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.filterField}>
          <span className={styles.filterLabel}>类别</span>
          <select className="select" value={family} onChange={(event) => setFamily(event.target.value)}>
            <option value="">全部</option>
            {familyOptions.map((item) => (
              <option key={item} value={item}>
                {formatFamilyLabel(item)}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.filterField}>
          <span className={styles.filterLabel}>排序</span>
          <select className="select" value={sort} onChange={(event) => setSort(event.target.value as SortOrder)}>
            <option value="desc">最新优先</option>
            <option value="asc">最早优先</option>
          </select>
        </label>
        <label className={styles.filterField}>
          <span className={styles.filterLabel}>开始日期</span>
          <input className="input" type="date" value={start} onChange={(event) => setStart(event.target.value)} />
        </label>
        <label className={styles.filterField}>
          <span className={styles.filterLabel}>结束日期</span>
          <input className="input" type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
        </label>
      </section>

      <section className="split-grid">
        <div className="card market-panel">
          <div className="section-headline">
            <div>
              <h2 className="section-title" style={{ marginBottom: 4 }}>
                已选指标
              </h2>
              <div className="helper">{selectedCard ? selectedCard.key : "从下方快照卡片中选择一张。"}</div>
            </div>
            {selectedCard ? <span className="kicker">{selectedCard.sourceLabel}</span> : null}
          </div>

          {seriesLoading ? (
            <div className="skeleton-stack">
              <span className="skeleton-line" data-width="medium" />
              <div className="skeleton-card" />
            </div>
          ) : null}
          {!seriesLoading && chartOption ? <ReactECharts option={chartOption} style={{ height: 320 }} /> : null}
          {!seriesLoading && !chartOption ? (
            <div className="surface-empty">
              <strong>无历史数据可绘制</strong>
              <div className="helper">调整筛选条件或选择其他快照卡片。</div>
            </div>
          ) : null}
        </div>

        <div className={`card market-panel ${styles.summaryBlock}`} data-tone="cool">
          <div className="section-headline">
            <div>
              <h2 className="section-title" style={{ marginBottom: 4 }}>
                概览
              </h2>
              <div className="helper">最新值、标准化得分和活跃指标的数据覆盖范围。</div>
            </div>
          </div>

          {!selectedCard ? (
            <div className="surface-empty">
              <strong>未选择指标</strong>
              <div className="helper">卡片和图表是联动的。选择一张快照卡片查看详情。</div>
            </div>
          ) : (
            <div className={styles.summaryGrid}>
              <div className={styles.summaryCard}>
                <div className="helper">指标</div>
                <div className="stock-card-title" style={{ marginTop: 8 }}>
                  {selectedCard.label}
                </div>
                <div className="helper" style={{ marginTop: 8 }}>
                  {selectedCard.countryLabel}
                </div>
              </div>
              <div className={styles.summaryCard}>
                <div className="helper">最新值</div>
                <div className="stock-score-value">{formatValue(selectedCard)}</div>
                <div className="helper" style={{ marginTop: 8 }}>
                  {selectedCard.date}
                </div>
                <div className="helper" style={{ marginTop: 4 }}>
                  {`完整值：${formatFullValue(selectedCard)}`}
                </div>
              </div>
              <div className={styles.summaryCard}>
                <div className="helper">得分</div>
                <div className="stock-score-value">{formatScore(latestPoint?.score ?? selectedCard.score)}</div>
                <div className="helper" style={{ marginTop: 8 }}>
                  {series ? `历史点数：${series.items.length}` : "历史未加载"}
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="card market-panel">
        <div className="section-headline">
          <div>
            <h2 className="section-title">宏观快照</h2>
            <div className="helper">世界银行与 AkShare 数据源的统一快照卡片。</div>
          </div>
          <div className="helper">{`${visibleCards.length} series`}</div>
        </div>

        {pagedSnapshots.items.length === 0 ? (
          <div className="surface-empty">
            <strong>无匹配结果</strong>
            <div className="helper">放宽关键词、国家或类别筛选条件。</div>
          </div>
        ) : (
          <>
            <div className={styles.snapshotGrid}>
              {pagedSnapshots.items.map((item) => {
                const active = item.key === selectedKey;
                const tone = item.source === "world_bank" ? "cool" : "warm";
                return (
                  <button
                    key={item.key}
                    type="button"
                    className={`card market-panel ${styles.snapshotCard}`}
                    data-tone={tone}
                    onClick={() => setSelectedKey(item.key)}
                    style={{
                      borderColor:
                        active && item.source === "world_bank"
                          ? "rgba(15, 118, 110, 0.35)"
                          : active
                            ? "rgba(194, 65, 12, 0.35)"
                            : undefined,
                    }}
                    title={`Full value: ${formatFullValue(item)}`}
                  >
                    <div className="card-title">{item.label}</div>
                    <div className="helper">{`${item.countryLabel} | ${item.sourceLabel}`}</div>
                    <div className={styles.snapshotValue}>{formatValue(item)}</div>
                    <div className="helper" style={{ marginTop: 6 }}>
                      {`完整值：${formatFullValue(item)}`}
                    </div>
                    <div className="helper" style={{ marginTop: 8 }}>
                      {`更新于 ${item.date}`}
                    </div>
                    <div className="helper" style={{ marginTop: 4 }}>
                      {`得分 ${formatScore(item.score)}`}
                    </div>
                  </button>
                );
              })}
            </div>

            <div className={`toolbar ${styles.pager}`} style={{ marginTop: 16 }}>
              <div className="helper">{`第 ${pagedSnapshots.page} / ${pagedSnapshots.maxPage} 页`}</div>
              <div className={styles.pagerActions}>
                <button
                  className="stock-page-button"
                  type="button"
                  disabled={pagedSnapshots.page <= 1}
                  onClick={() => setSnapshotPage((value) => value - 1)}
                >
                  上一页
                </button>
                <button
                  className="stock-page-button"
                  type="button"
                  disabled={pagedSnapshots.page >= pagedSnapshots.maxPage}
                  onClick={() => setSnapshotPage((value) => value + 1)}
                >
                  下一页
                </button>
              </div>
            </div>
          </>
        )}
      </section>

      <section className={styles.referenceSection}>
        <div className={styles.referenceIntro}>
          <div>
            <span className="kicker">跨市场行情</span>
            <h2 className="section-title" style={{ marginTop: 8, marginBottom: 4 }}>
              参考面板
            </h2>
            <div className="helper">外汇和债券行情现在通过统一的虚拟化表格模式渲染。</div>
          </div>
          <div className={styles.referenceSummary}>
            <div className={styles.referenceSummaryCard}>
              <span className={styles.referenceSummaryLabel}>面板数</span>
              <strong className={styles.referenceSummaryValue}>{referencePanelCount}</strong>
            </div>
            <div className={styles.referenceSummaryCard}>
              <span className={styles.referenceSummaryLabel}>已加载</span>
              <strong className={styles.referenceSummaryValue}>{referenceReadyCount}</strong>
            </div>
            <div className={styles.referenceSummaryCard}>
              <span className={styles.referenceSummaryLabel}>行数</span>
              <strong className={styles.referenceSummaryValue}>{referenceLoadedRows}</strong>
            </div>
          </div>
        </div>

        <div className={styles.referenceGrid}>
          <ReferenceTableCard
            eyebrow="外汇现货"
            tone="cool"
            title="外汇现货报价"
            helper="可滚动外汇现货报价，提供更深入的跨市场参考。"
            total={referencePanels.fxSpot.total}
            loading={referencePanels.fxSpot.loading}
            error={referencePanels.fxSpot.error}
            emptyMessage="暂无外汇现货报价。"
          >
            <ReferenceVirtualTable
              rows={referencePanels.fxSpot.items}
              rowKey={(item) => `${item.currency_pair}-${item.as_of || "spot"}`}
              columns={[
                { key: "currency_pair", header: "货币对", width: "1.1fr", cell: (item) => item.currency_pair },
                { key: "bid", header: "买入价", align: "right", cell: (item) => formatNullableNumber(item.bid, 4) },
                { key: "ask", header: "卖出价", align: "right", cell: (item) => formatNullableNumber(item.ask, 4) },
                { key: "as_of", header: "更新时间", width: "1.2fr", cell: (item) => formatDateTime(item.as_of) },
              ]}
            />
          </ReferenceTableCard>

          <ReferenceTableCard
            eyebrow="外汇掉期"
            tone="cool"
            title="外汇掉期曲线"
            helper="1周、1月、3月期限的紧凑虚拟化表格。"
            total={referencePanels.fxSwap.total}
            loading={referencePanels.fxSwap.loading}
            error={referencePanels.fxSwap.error}
            emptyMessage="暂无外汇掉期报价。"
          >
            <ReferenceVirtualTable
              rows={referencePanels.fxSwap.items}
              rowKey={(item) => `${item.currency_pair}-${item.as_of || "swap"}`}
              columns={[
                { key: "currency_pair", header: "货币对", width: "1.1fr", cell: (item) => item.currency_pair },
                { key: "one_week", header: "1周", align: "right", cell: (item) => formatNullableNumber(item.one_week, 2) },
                { key: "one_month", header: "1月", align: "right", cell: (item) => formatNullableNumber(item.one_month, 2) },
                {
                  key: "three_month",
                  header: "3月",
                  align: "right",
                  cell: (item) => formatNullableNumber(item.three_month, 2),
                },
              ]}
            />
          </ReferenceTableCard>

          <ReferenceTableCard
            eyebrow="交叉外汇"
            tone="cool"
            title="交叉外汇报价"
            helper="与人民币货币对分离的交叉汇率，便于查看。"
            total={referencePanels.fxPair.total}
            loading={referencePanels.fxPair.loading}
            error={referencePanels.fxPair.error}
            emptyMessage="暂无交叉外汇报价。"
          >
            <ReferenceVirtualTable
              rows={referencePanels.fxPair.items}
              rowKey={(item) => `${item.currency_pair}-${item.as_of || "pair"}`}
              columns={[
                { key: "currency_pair", header: "货币对", width: "1.1fr", cell: (item) => item.currency_pair },
                { key: "bid", header: "买入价", align: "right", cell: (item) => formatNullableNumber(item.bid, 4) },
                { key: "ask", header: "卖出价", align: "right", cell: (item) => formatNullableNumber(item.ask, 4) },
                { key: "as_of", header: "更新时间", width: "1.2fr", cell: (item) => formatDateTime(item.as_of) },
              ]}
            />
          </ReferenceTableCard>

          <ReferenceTableCard
            eyebrow="债券成交"
            tone="warm"
            title="债券成交行情"
            helper="最新的债券交易，包含净价、收益率和成交量。"
            total={referencePanels.bondTrades.total}
            loading={referencePanels.bondTrades.loading}
            error={referencePanels.bondTrades.error}
            emptyMessage="暂无债券成交行情。"
          >
            <ReferenceVirtualTable
              rows={referencePanels.bondTrades.items}
              rowKey={(item) => `${item.bond_name}-${item.as_of || "trade"}`}
              columns={[
                { key: "bond_name", header: "债券", width: "1.3fr", cell: (item) => item.bond_name },
                {
                  key: "deal_net_price",
                  header: "净价",
                  align: "right",
                  cell: (item) => formatNullableNumber(item.deal_net_price, 3),
                },
                {
                  key: "latest_yield",
                  header: "收益率",
                  align: "right",
                  cell: (item) => formatLoosePercent(item.latest_yield),
                },
                { key: "volume", header: "成交量", align: "right", cell: (item) => formatNullableNumber(item.volume, 0) },
              ]}
            />
          </ReferenceTableCard>

          <ReferenceTableCard
            eyebrow="债券报价"
            tone="warm"
            title="债券报价"
            helper="报价来源、买入净价和买入收益率的紧凑表格。"
            total={referencePanels.bondQuotes.total}
            loading={referencePanels.bondQuotes.loading}
            error={referencePanels.bondQuotes.error}
            emptyMessage="暂无债券报价数据。"
          >
            <ReferenceVirtualTable
              rows={referencePanels.bondQuotes.items}
              rowKey={(item) => `${item.bond_name}-${item.quote_org || "quote"}-${item.as_of || "quote"}`}
              columns={[
                { key: "bond_name", header: "债券", width: "1.2fr", cell: (item) => item.bond_name },
                { key: "quote_org", header: "报价机构", width: "1.2fr", cell: (item) => item.quote_org || "--" },
                {
                  key: "buy_net_price",
                  header: "买入价",
                  align: "right",
                  cell: (item) => formatNullableNumber(item.buy_net_price, 3),
                },
                {
                  key: "buy_yield",
                  header: "买入收益率",
                  align: "right",
                  cell: (item) => formatLoosePercent(item.buy_yield),
                },
              ]}
            />
          </ReferenceTableCard>
        </div>
      </section>
    </div>
  );
}
