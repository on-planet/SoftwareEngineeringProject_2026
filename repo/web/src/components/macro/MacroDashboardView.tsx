import React from "react";
import ReactECharts from "echarts-for-react";

import { MacroDashboardModel } from "../../hooks/useMacroDashboard";
import { formatLoosePercent, formatNullableNumber } from "../../utils/format";
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
          <strong>数据加载失败</strong>
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
            <strong>宏观数据加载失败</strong>
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
            <span className="kicker">Macro Deck</span>
            <h1 className="page-title">宏观数据看板</h1>
            <p className={styles.heroDescription}>
              世界银行核心口径与 AkShare 扩展指标统一汇总为同一张快照卡片墙，序列详情和筛选体验也做了统一。
            </p>
          </div>
        </div>
        <div className={styles.heroMetrics}>
          <div className={styles.heroMetric}>
            <div className={styles.heroMetricLabel}>可用序列</div>
            <div className={styles.heroMetricValue}>{cards.length}</div>
            <div className={styles.heroMetricHelper}>去重后按指标键聚合</div>
          </div>
          <div className={styles.heroMetric}>
            <div className={styles.heroMetricLabel}>当前筛选结果</div>
            <div className={styles.heroMetricValue}>{visibleCards.length}</div>
            <div className={styles.heroMetricHelper}>卡片列表和序列详情使用同一筛选状态</div>
          </div>
          <div className={styles.heroMetric}>
            <div className={styles.heroMetricLabel}>当前选中</div>
            <div className={styles.heroMetricValue}>{selectedCard ? selectedCard.label : "--"}</div>
            <div className={styles.heroMetricHelper}>{selectedCard ? selectedCard.countryLabel : "请选择一个序列"}</div>
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
            placeholder="GDP / CPI / 非农 / 中国"
          />
        </label>
        <label className={styles.filterField}>
          <span className={styles.filterLabel}>国家或地区</span>
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
          <span className={styles.filterLabel}>指标类别</span>
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
          <span className={styles.filterLabel}>序列开始日期</span>
          <input className="input" type="date" value={start} onChange={(event) => setStart(event.target.value)} />
        </label>
        <label className={styles.filterField}>
          <span className={styles.filterLabel}>序列结束日期</span>
          <input className="input" type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
        </label>
      </section>

      <section className="split-grid">
        <div className="card market-panel">
          <div className="section-headline">
            <div>
              <h2 className="section-title" style={{ marginBottom: 4 }}>
                当前序列
              </h2>
              <div className="helper">{selectedCard ? selectedCard.key : "从下方快照卡片中选择一条序列"}</div>
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
              <strong>暂无可展示序列</strong>
              <div className="helper">当前筛选条件下没有找到可用的历史时间序列。</div>
            </div>
          ) : null}
        </div>

        <div className={`card market-panel ${styles.summaryBlock}`} data-tone="cool">
          <div className="section-headline">
            <div>
              <h2 className="section-title" style={{ marginBottom: 4 }}>
                关键摘要
              </h2>
              <div className="helper">当前所选宏观序列的最新快照与评分。</div>
            </div>
          </div>

          {!selectedCard ? (
            <div className="surface-empty">
              <strong>请选择一条序列</strong>
              <div className="helper">卡片与图表是联动的，选择卡片后会自动加载右侧摘要和历史曲线。</div>
            </div>
          ) : (
            <div className={styles.summaryGrid}>
              <div className={styles.summaryCard}>
                <div className="helper">指标名称</div>
                <div className="stock-card-title" style={{ marginTop: 8 }}>
                  {selectedCard.label}
                </div>
                <div className="helper" style={{ marginTop: 8 }}>
                  {selectedCard.countryLabel}
                </div>
              </div>
              <div className={styles.summaryCard}>
                <div className="helper">最新数值</div>
                <div className="stock-score-value">{formatValue(selectedCard)}</div>
                <div className="helper" style={{ marginTop: 8 }}>
                  {selectedCard.date}
                </div>
                <div className="helper" style={{ marginTop: 4 }}>
                  {`完整值：${formatFullValue(selectedCard)}`}
                </div>
              </div>
              <div className={styles.summaryCard}>
                <div className="helper">最新评分</div>
                <div className="stock-score-value">{formatScore(latestPoint?.score ?? selectedCard.score)}</div>
                <div className="helper" style={{ marginTop: 8 }}>
                  {series ? `已加载 ${series.items.length} 个历史点` : "尚未加载历史序列"}
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
            <div className="helper">世界银行与 AkShare 的最新快照统一展示，点击卡片即可切换右侧图表。</div>
          </div>
          <div className="helper">{`${visibleCards.length} 个序列`}</div>
        </div>

        {pagedSnapshots.items.length === 0 ? (
          <div className="surface-empty">
            <strong>当前筛选下没有结果</strong>
            <div className="helper">可以放宽关键词、国家或指标类别筛选条件。</div>
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
                      borderColor: active
                        ? item.source === "world_bank"
                          ? "rgba(15, 118, 110, 0.35)"
                          : "rgba(194, 65, 12, 0.35)"
                        : undefined,
                    }}
                    title={`完整值：${formatFullValue(item)}`}
                  >
                    <div className="card-title">{item.label}</div>
                    <div className="helper">{`${item.countryLabel} · ${item.sourceLabel}`}</div>
                    <div className={styles.snapshotValue}>{formatValue(item)}</div>
                    <div className="helper" style={{ marginTop: 6 }}>
                      {`完整值：${formatFullValue(item)}`}
                    </div>
                    <div className="helper" style={{ marginTop: 8 }}>
                      {`更新于 ${item.date}`}
                    </div>
                    <div className="helper" style={{ marginTop: 4 }}>
                      {`评分 ${formatScore(item.score)}`}
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
            <span className="kicker">Cross-Market Tape</span>
            <h2 className="section-title" style={{ marginTop: 8, marginBottom: 4 }}>
              Reference Panels
            </h2>
            <div className="helper">FX and bond reference feeds are grouped into one compact macro workspace.</div>
          </div>
          <div className={styles.referenceSummary}>
            <div className={styles.referenceSummaryCard}>
              <span className={styles.referenceSummaryLabel}>Panels</span>
              <strong className={styles.referenceSummaryValue}>{referencePanelCount}</strong>
            </div>
            <div className={styles.referenceSummaryCard}>
              <span className={styles.referenceSummaryLabel}>Loaded</span>
              <strong className={styles.referenceSummaryValue}>{referenceReadyCount}</strong>
            </div>
            <div className={styles.referenceSummaryCard}>
              <span className={styles.referenceSummaryLabel}>Rows</span>
              <strong className={styles.referenceSummaryValue}>{referenceLoadedRows}</strong>
            </div>
          </div>
        </div>
        <div className={styles.referenceGrid}>
        <ReferenceTableCard
          eyebrow="FX Spot"
          tone="cool"
          title="人民币即期报价"
          helper="新接入的外汇接口会直接展示在这个面板里。"
          total={referencePanels.fxSpot.total}
          loading={referencePanels.fxSpot.loading}
          error={referencePanels.fxSpot.error}
          emptyMessage="后端尚未抓到人民币即期报价数据。"
        >
          <table className="data-table dense-table">
            <thead>
              <tr>
                <th>货币对</th>
                <th>买价</th>
                <th>卖价</th>
                <th>更新时间</th>
              </tr>
            </thead>
            <tbody>
              {referencePanels.fxSpot.items.map((item) => (
                <tr key={`${item.currency_pair}-${item.as_of || "spot"}`}>
                  <td>{item.currency_pair}</td>
                  <td>{formatNullableNumber(item.bid, 4)}</td>
                  <td>{formatNullableNumber(item.ask, 4)}</td>
                  <td>{formatDateTime(item.as_of)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ReferenceTableCard>

        <ReferenceTableCard
          title="人民币远掉报价"
          helper="默认展示 1 周、1 月和 3 月几个主要期限。"
          eyebrow="FX Swap"
          tone="cool"
          total={referencePanels.fxSwap.total}
          loading={referencePanels.fxSwap.loading}
          error={referencePanels.fxSwap.error}
          emptyMessage="后端尚未抓到人民币远掉报价数据。"
        >
          <table className="data-table dense-table">
            <thead>
              <tr>
                <th>货币对</th>
                <th>1周</th>
                <th>1月</th>
                <th>3月</th>
              </tr>
            </thead>
            <tbody>
              {referencePanels.fxSwap.items.map((item) => (
                <tr key={`${item.currency_pair}-${item.as_of || "swap"}`}>
                  <td>{item.currency_pair}</td>
                  <td>{formatNullableNumber(item.one_week, 2)}</td>
                  <td>{formatNullableNumber(item.one_month, 2)}</td>
                  <td>{formatNullableNumber(item.three_month, 2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ReferenceTableCard>

        <ReferenceTableCard
          title="外币对即期报价"
          helper="和人民币报价拆开显示，避免同屏混排。"
          eyebrow="FX Pair"
          tone="cool"
          total={referencePanels.fxPair.total}
          loading={referencePanels.fxPair.loading}
          error={referencePanels.fxPair.error}
          emptyMessage="后端尚未抓到外币对即期报价数据。"
        >
          <table className="data-table dense-table">
            <thead>
              <tr>
                <th>货币对</th>
                <th>买价</th>
                <th>卖价</th>
                <th>更新时间</th>
              </tr>
            </thead>
            <tbody>
              {referencePanels.fxPair.items.map((item) => (
                <tr key={`${item.currency_pair}-${item.as_of || "pair"}`}>
                  <td>{item.currency_pair}</td>
                  <td>{formatNullableNumber(item.bid, 4)}</td>
                  <td>{formatNullableNumber(item.ask, 4)}</td>
                  <td>{formatDateTime(item.as_of)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ReferenceTableCard>

        <ReferenceTableCard
          title="银行间现券成交"
          helper="中债现券成交行情直接放在宏观页，不再缺债券板块。"
          eyebrow="Bond Trade"
          tone="warm"
          total={referencePanels.bondTrades.total}
          loading={referencePanels.bondTrades.loading}
          error={referencePanels.bondTrades.error}
          emptyMessage="后端尚未抓到现券成交行情数据。"
        >
          <table className="data-table dense-table">
            <thead>
              <tr>
                <th>债券</th>
                <th>净价</th>
                <th>收益率</th>
                <th>成交量</th>
              </tr>
            </thead>
            <tbody>
              {referencePanels.bondTrades.items.map((item) => (
                <tr key={`${item.bond_name}-${item.as_of || "trade"}`}>
                  <td>{item.bond_name}</td>
                  <td>{formatNullableNumber(item.deal_net_price, 3)}</td>
                  <td>{formatLoosePercent(item.latest_yield)}</td>
                  <td>{formatNullableNumber(item.volume, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ReferenceTableCard>

        <ReferenceTableCard
          title="银行间做市报价"
          helper="补上报价机构、净价和收益率三个核心字段。"
          eyebrow="Bond Quote"
          tone="warm"
          total={referencePanels.bondQuotes.total}
          loading={referencePanels.bondQuotes.loading}
          error={referencePanels.bondQuotes.error}
          emptyMessage="后端尚未抓到做市报价数据。"
        >
          <table className="data-table dense-table">
            <thead>
              <tr>
                <th>债券</th>
                <th>机构</th>
                <th>买入净价</th>
                <th>买入收益率</th>
              </tr>
            </thead>
            <tbody>
              {referencePanels.bondQuotes.items.map((item) => (
                <tr key={`${item.bond_name}-${item.quote_org || "quote"}-${item.as_of || "quote"}`}>
                  <td>{item.bond_name}</td>
                  <td>{item.quote_org || "--"}</td>
                  <td>{formatNullableNumber(item.buy_net_price, 3)}</td>
                  <td>{formatLoosePercent(item.buy_yield)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </ReferenceTableCard>
        </div>
      </section>
    </div>
  );
}
