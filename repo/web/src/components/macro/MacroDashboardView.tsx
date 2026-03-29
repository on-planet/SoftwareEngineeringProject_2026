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
        <div className="helper">{loading ? "Loading..." : `${total} rows`}</div>
      </div>
      {loading ? (
        <div className="skeleton-stack">
          <span className="skeleton-line" data-width="medium" />
          <div className="skeleton-card" />
        </div>
      ) : null}
      {!loading && error ? (
        <div className="surface-empty">
          <strong>Reference panel failed</strong>
          <div className="helper">{error}</div>
        </div>
      ) : null}
      {!loading && !error && total === 0 ? (
        <div className="surface-empty">
          <strong>No data</strong>
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
            <strong>Macro snapshot failed</strong>
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
            <h1 className="page-title">Macro Dashboard</h1>
            <p className={styles.heroDescription}>
              World Bank and AkShare indicators are normalized into one workspace with linked cards, charts, and reference tables.
            </p>
          </div>
        </div>
        <div className={styles.heroMetrics}>
          <div className={styles.heroMetric}>
            <div className={styles.heroMetricLabel}>Series</div>
            <div className={styles.heroMetricValue}>{cards.length}</div>
            <div className={styles.heroMetricHelper}>Distinct keys after snapshot merge</div>
          </div>
          <div className={styles.heroMetric}>
            <div className={styles.heroMetricLabel}>Visible</div>
            <div className={styles.heroMetricValue}>{visibleCards.length}</div>
            <div className={styles.heroMetricHelper}>Filtered cards and linked chart scope</div>
          </div>
          <div className={styles.heroMetric}>
            <div className={styles.heroMetricLabel}>Selected</div>
            <div className={styles.heroMetricValue}>{selectedCard ? selectedCard.label : "--"}</div>
            <div className={styles.heroMetricHelper}>{selectedCard ? selectedCard.countryLabel : "Choose a series"}</div>
          </div>
        </div>
      </section>

      <section className={`toolbar sticky-filter-bar ${styles.stickyBar}`}>
        <label className={styles.filterField}>
          <span className={styles.filterLabel}>Search</span>
          <input
            className="input"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="GDP / CPI / payrolls / China"
          />
        </label>
        <label className={styles.filterField}>
          <span className={styles.filterLabel}>Country</span>
          <select className="select" value={country} onChange={(event) => setCountry(event.target.value)}>
            <option value="">All</option>
            {countryOptions.map((item) => (
              <option key={item} value={item}>
                {COUNTRY_LABELS[item] || item}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.filterField}>
          <span className={styles.filterLabel}>Family</span>
          <select className="select" value={family} onChange={(event) => setFamily(event.target.value)}>
            <option value="">All</option>
            {familyOptions.map((item) => (
              <option key={item} value={item}>
                {formatFamilyLabel(item)}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.filterField}>
          <span className={styles.filterLabel}>Sort</span>
          <select className="select" value={sort} onChange={(event) => setSort(event.target.value as SortOrder)}>
            <option value="desc">Latest First</option>
            <option value="asc">Oldest First</option>
          </select>
        </label>
        <label className={styles.filterField}>
          <span className={styles.filterLabel}>Start</span>
          <input className="input" type="date" value={start} onChange={(event) => setStart(event.target.value)} />
        </label>
        <label className={styles.filterField}>
          <span className={styles.filterLabel}>End</span>
          <input className="input" type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
        </label>
      </section>

      <section className="split-grid">
        <div className="card market-panel">
          <div className="section-headline">
            <div>
              <h2 className="section-title" style={{ marginBottom: 4 }}>
                Selected Series
              </h2>
              <div className="helper">{selectedCard ? selectedCard.key : "Choose a card from the snapshot deck below."}</div>
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
              <strong>No history to plot</strong>
              <div className="helper">Adjust filters or select another snapshot card.</div>
            </div>
          ) : null}
        </div>

        <div className={`card market-panel ${styles.summaryBlock}`} data-tone="cool">
          <div className="section-headline">
            <div>
              <h2 className="section-title" style={{ marginBottom: 4 }}>
                Summary
              </h2>
              <div className="helper">Latest value, normalized score, and series coverage for the active indicator.</div>
            </div>
          </div>

          {!selectedCard ? (
            <div className="surface-empty">
              <strong>No series selected</strong>
              <div className="helper">Cards and chart are linked. Select a snapshot card to inspect details.</div>
            </div>
          ) : (
            <div className={styles.summaryGrid}>
              <div className={styles.summaryCard}>
                <div className="helper">Indicator</div>
                <div className="stock-card-title" style={{ marginTop: 8 }}>
                  {selectedCard.label}
                </div>
                <div className="helper" style={{ marginTop: 8 }}>
                  {selectedCard.countryLabel}
                </div>
              </div>
              <div className={styles.summaryCard}>
                <div className="helper">Latest Value</div>
                <div className="stock-score-value">{formatValue(selectedCard)}</div>
                <div className="helper" style={{ marginTop: 8 }}>
                  {selectedCard.date}
                </div>
                <div className="helper" style={{ marginTop: 4 }}>
                  {`Full value: ${formatFullValue(selectedCard)}`}
                </div>
              </div>
              <div className={styles.summaryCard}>
                <div className="helper">Score</div>
                <div className="stock-score-value">{formatScore(latestPoint?.score ?? selectedCard.score)}</div>
                <div className="helper" style={{ marginTop: 8 }}>
                  {series ? `History points: ${series.items.length}` : "History not loaded"}
                </div>
              </div>
            </div>
          )}
        </div>
      </section>

      <section className="card market-panel">
        <div className="section-headline">
          <div>
            <h2 className="section-title">Macro Snapshot</h2>
            <div className="helper">Unified snapshot cards across World Bank and AkShare data sources.</div>
          </div>
          <div className="helper">{`${visibleCards.length} series`}</div>
        </div>

        {pagedSnapshots.items.length === 0 ? (
          <div className="surface-empty">
            <strong>No matches</strong>
            <div className="helper">Relax keyword, country, or family filters.</div>
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
                      {`Full value: ${formatFullValue(item)}`}
                    </div>
                    <div className="helper" style={{ marginTop: 8 }}>
                      {`Updated ${item.date}`}
                    </div>
                    <div className="helper" style={{ marginTop: 4 }}>
                      {`Score ${formatScore(item.score)}`}
                    </div>
                  </button>
                );
              })}
            </div>

            <div className={`toolbar ${styles.pager}`} style={{ marginTop: 16 }}>
              <div className="helper">{`Page ${pagedSnapshots.page} / ${pagedSnapshots.maxPage}`}</div>
              <div className={styles.pagerActions}>
                <button
                  className="stock-page-button"
                  type="button"
                  disabled={pagedSnapshots.page <= 1}
                  onClick={() => setSnapshotPage((value) => value - 1)}
                >
                  Prev
                </button>
                <button
                  className="stock-page-button"
                  type="button"
                  disabled={pagedSnapshots.page >= pagedSnapshots.maxPage}
                  onClick={() => setSnapshotPage((value) => value + 1)}
                >
                  Next
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
            <div className="helper">FX and bond feeds now render through one virtualized table pattern.</div>
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
            title="FX Spot Quotes"
            helper="Scrollable FX spot quotes for deeper cross-market context."
            total={referencePanels.fxSpot.total}
            loading={referencePanels.fxSpot.loading}
            error={referencePanels.fxSpot.error}
            emptyMessage="No FX spot quotes returned."
          >
            <ReferenceVirtualTable
              rows={referencePanels.fxSpot.items}
              rowKey={(item) => `${item.currency_pair}-${item.as_of || "spot"}`}
              columns={[
                { key: "currency_pair", header: "Pair", width: "1.1fr", cell: (item) => item.currency_pair },
                { key: "bid", header: "Bid", align: "right", cell: (item) => formatNullableNumber(item.bid, 4) },
                { key: "ask", header: "Ask", align: "right", cell: (item) => formatNullableNumber(item.ask, 4) },
                { key: "as_of", header: "Updated", width: "1.2fr", cell: (item) => formatDateTime(item.as_of) },
              ]}
            />
          </ReferenceTableCard>

          <ReferenceTableCard
            eyebrow="FX Swap"
            tone="cool"
            title="FX Swap Curves"
            helper="1W, 1M, and 3M tenors in a dense virtualized table."
            total={referencePanels.fxSwap.total}
            loading={referencePanels.fxSwap.loading}
            error={referencePanels.fxSwap.error}
            emptyMessage="No FX swap quotes returned."
          >
            <ReferenceVirtualTable
              rows={referencePanels.fxSwap.items}
              rowKey={(item) => `${item.currency_pair}-${item.as_of || "swap"}`}
              columns={[
                { key: "currency_pair", header: "Pair", width: "1.1fr", cell: (item) => item.currency_pair },
                { key: "one_week", header: "1W", align: "right", cell: (item) => formatNullableNumber(item.one_week, 2) },
                { key: "one_month", header: "1M", align: "right", cell: (item) => formatNullableNumber(item.one_month, 2) },
                {
                  key: "three_month",
                  header: "3M",
                  align: "right",
                  cell: (item) => formatNullableNumber(item.three_month, 2),
                },
              ]}
            />
          </ReferenceTableCard>

          <ReferenceTableCard
            eyebrow="FX Pair"
            tone="cool"
            title="Cross FX Quotes"
            helper="Cross rates separated from CNY pairs for cleaner scanning."
            total={referencePanels.fxPair.total}
            loading={referencePanels.fxPair.loading}
            error={referencePanels.fxPair.error}
            emptyMessage="No cross FX quotes returned."
          >
            <ReferenceVirtualTable
              rows={referencePanels.fxPair.items}
              rowKey={(item) => `${item.currency_pair}-${item.as_of || "pair"}`}
              columns={[
                { key: "currency_pair", header: "Pair", width: "1.1fr", cell: (item) => item.currency_pair },
                { key: "bid", header: "Bid", align: "right", cell: (item) => formatNullableNumber(item.bid, 4) },
                { key: "ask", header: "Ask", align: "right", cell: (item) => formatNullableNumber(item.ask, 4) },
                { key: "as_of", header: "Updated", width: "1.2fr", cell: (item) => formatDateTime(item.as_of) },
              ]}
            />
          </ReferenceTableCard>

          <ReferenceTableCard
            eyebrow="Bond Trade"
            tone="warm"
            title="Bond Trade Tape"
            helper="Latest bond transactions with net price, yield, and volume."
            total={referencePanels.bondTrades.total}
            loading={referencePanels.bondTrades.loading}
            error={referencePanels.bondTrades.error}
            emptyMessage="No bond trade tape returned."
          >
            <ReferenceVirtualTable
              rows={referencePanels.bondTrades.items}
              rowKey={(item) => `${item.bond_name}-${item.as_of || "trade"}`}
              columns={[
                { key: "bond_name", header: "Bond", width: "1.3fr", cell: (item) => item.bond_name },
                {
                  key: "deal_net_price",
                  header: "Net Price",
                  align: "right",
                  cell: (item) => formatNullableNumber(item.deal_net_price, 3),
                },
                {
                  key: "latest_yield",
                  header: "Yield",
                  align: "right",
                  cell: (item) => formatLoosePercent(item.latest_yield),
                },
                { key: "volume", header: "Volume", align: "right", cell: (item) => formatNullableNumber(item.volume, 0) },
              ]}
            />
          </ReferenceTableCard>

          <ReferenceTableCard
            eyebrow="Bond Quote"
            tone="warm"
            title="Bond Quotes"
            helper="Quote source, bid net price, and bid yield in one compact table."
            total={referencePanels.bondQuotes.total}
            loading={referencePanels.bondQuotes.loading}
            error={referencePanels.bondQuotes.error}
            emptyMessage="No bond quote rows returned."
          >
            <ReferenceVirtualTable
              rows={referencePanels.bondQuotes.items}
              rowKey={(item) => `${item.bond_name}-${item.quote_org || "quote"}-${item.as_of || "quote"}`}
              columns={[
                { key: "bond_name", header: "Bond", width: "1.2fr", cell: (item) => item.bond_name },
                { key: "quote_org", header: "Quote Org", width: "1.2fr", cell: (item) => item.quote_org || "--" },
                {
                  key: "buy_net_price",
                  header: "Bid Price",
                  align: "right",
                  cell: (item) => formatNullableNumber(item.buy_net_price, 3),
                },
                {
                  key: "buy_yield",
                  header: "Bid Yield",
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
