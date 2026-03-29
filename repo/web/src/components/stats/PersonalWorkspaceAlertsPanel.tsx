import React, { useEffect, useMemo, useState } from "react";

import { AnimatedNumber } from "../motion/AnimatedNumber";
import { useApiQuery } from "../../hooks/useApiQuery";
import { useAuth } from "../../providers/AuthProvider";
import {
  AlertPriceOperator,
  AlertResearchKind,
  AlertRuleType,
} from "../../services/api";
import {
  DEFAULT_ALERT_LOOKBACK_DAYS,
  buildAlertCenterDomainQueryKey,
  buildAlertDefaultThreshold,
  buildAlertReadableExplanation,
  buildAlertRuleSummary,
  createAlertRule,
  dedupeAlertSymbols,
  getAlertCenterDomainQueryOptions,
  loadAlertCenter,
  normalizeAlertSymbol,
  removeAlertRule,
  setAlertRuleEnabled,
} from "../../domain/alerts";

import styles from "./WorkspacePanels.module.css";

type PersonalWorkspaceAlertsPanelProps = {
  scopeLabel: string;
  symbols: string[];
  activeSymbol?: string;
  onFocusSymbolChange?: (symbol: string) => void;
};

export function PersonalWorkspaceAlertsPanel({
  scopeLabel,
  symbols,
  activeSymbol,
  onFocusSymbolChange,
}: PersonalWorkspaceAlertsPanelProps) {
  const { isAuthenticated, token } = useAuth();
  const [ruleType, setRuleType] = useState<AlertRuleType>("price");
  const [name, setName] = useState("");
  const [draftSymbol, setDraftSymbol] = useState("");
  const [filterSymbol, setFilterSymbol] = useState("");
  const [priceOperator, setPriceOperator] = useState<AlertPriceOperator>("gte");
  const [threshold, setThreshold] = useState(buildAlertDefaultThreshold("price"));
  const [eventType, setEventType] = useState("buyback");
  const [researchKind, setResearchKind] = useState<AlertResearchKind>("all");
  const [lookbackDays, setLookbackDays] = useState(DEFAULT_ALERT_LOOKBACK_DAYS);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyRuleId, setBusyRuleId] = useState<number | null>(null);

  const normalizedSymbols = useMemo(() => dedupeAlertSymbols(symbols), [symbols]);
  const activeScopeSymbol = useMemo(() => {
    const normalized = normalizeAlertSymbol(activeSymbol || "");
    return normalizedSymbols.includes(normalized) ? normalized : "";
  }, [activeSymbol, normalizedSymbols]);

  useEffect(() => {
    const fallback = activeScopeSymbol || normalizedSymbols[0] || "";
    setDraftSymbol((current) => {
      const normalized = normalizeAlertSymbol(current);
      if (normalized && normalizedSymbols.includes(normalized)) {
        return normalized;
      }
      return fallback;
    });
    setFilterSymbol((current) => {
      const normalized = normalizeAlertSymbol(current);
      if (activeScopeSymbol) {
        return activeScopeSymbol;
      }
      if (normalized && normalizedSymbols.includes(normalized)) {
        return normalized;
      }
      return "";
    });
  }, [activeScopeSymbol, normalizedSymbols]);
  const alertCenterQueryKey =
    isAuthenticated && token ? buildAlertCenterDomainQueryKey(token) : null;

  const centerQuery = useApiQuery(
    alertCenterQueryKey,
    () => loadAlertCenter(token as string),
    getAlertCenterDomainQueryOptions(),
  );

  const scopedItems = useMemo(
    () =>
      (centerQuery.data?.items || []).filter((item) =>
        normalizedSymbols.includes(normalizeAlertSymbol(item.symbol)),
      ),
    [centerQuery.data?.items, normalizedSymbols],
  );

  const visibleItems = useMemo(
    () =>
      filterSymbol
        ? scopedItems.filter((item) => normalizeAlertSymbol(item.symbol) === filterSymbol)
        : scopedItems,
    [filterSymbol, scopedItems],
  );

  const triggeredCount = scopedItems.filter((item) => item.triggered).length;
  const coveredSymbols = new Set(scopedItems.map((item) => normalizeAlertSymbol(item.symbol))).size;

  const handleCreateRule = async () => {
    if (!token || !isAuthenticated) {
      setActionError("登录后才能创建告警规则。");
      return;
    }
    const normalizedName = name.trim();
    const normalizedDraftSymbol = normalizeAlertSymbol(draftSymbol);
    if (!normalizedName || !normalizedDraftSymbol) {
      setActionError("请填写规则名称并选择服务标的。");
      return;
    }
    if (ruleType === "price" && (!threshold || Number(threshold) <= 0)) {
      setActionError("价格规则需要大于 0 的阈值。");
      return;
    }
    if (ruleType === "event" && !eventType.trim()) {
      setActionError("事件规则需要事件类型。");
      return;
    }
    try {
      await createAlertRule(token, {
        name: normalizedName,
        symbol: normalizedDraftSymbol,
        ruleType,
        priceOperator,
        threshold,
        eventType,
        researchKind,
        lookbackDays,
      });
      setName("");
      setThreshold(buildAlertDefaultThreshold(ruleType));
      setActionError(null);
      await centerQuery.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "创建告警失败");
    }
  };

  const handleToggleRule = async (ruleId: number, current: boolean) => {
    if (!token || !isAuthenticated) {
      return;
    }
    setBusyRuleId(ruleId);
    try {
      await setAlertRuleEnabled(token, ruleId, !current);
      setActionError(null);
      await centerQuery.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "更新告警失败");
    } finally {
      setBusyRuleId(null);
    }
  };

  const handleDeleteRule = async (ruleId: number) => {
    if (!token || !isAuthenticated) {
      return;
    }
    setBusyRuleId(ruleId);
    try {
      await removeAlertRule(token, ruleId);
      setActionError(null);
      await centerQuery.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "删除告警失败");
    } finally {
      setBusyRuleId(null);
    }
  };

  if (normalizedSymbols.length === 0) {
    return (
      <div className="surface-empty">
        <strong>{`${scopeLabel}还没有可服务的标的`}</strong>
        <div className="helper">先补充自选或已买记录，再为这批标的配置告警规则。</div>
      </div>
    );
  }

  return (
    <div className={styles.stack}>
      <div className={styles.summary}>
        <div className={styles.summaryText}>
          <div className="card-title">{`${scopeLabel}告警工作台`}</div>
          <div className="helper">
            规则只围绕当前{scopeLabel}集合展示和创建。你可以先按标的聚焦，再切价格、事件或财报提醒。
          </div>
        </div>
        <div className={styles.metrics}>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>服务标的</div>
            <div className={styles.metricValue}>
              <AnimatedNumber value={normalizedSymbols.length} />
            </div>
            <div className={styles.metricHelper}>{scopeLabel}</div>
          </div>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>规则总数</div>
            <div className={styles.metricValue}>
              <AnimatedNumber value={scopedItems.length} />
            </div>
            <div className={styles.metricHelper}>{`${coveredSymbols} 个标的已配置`}</div>
          </div>
          <div className={styles.metric}>
            <div className={styles.metricLabel}>当前触发</div>
            <div className={styles.metricValue}>
              <AnimatedNumber value={triggeredCount} />
            </div>
            <div className={styles.metricHelper}>{filterSymbol || "全部标的"}</div>
          </div>
        </div>
      </div>

      <div className={styles.layout}>
        <section className="card market-panel">
          <div className="card-title" style={{ marginBottom: 12 }}>
            新建规则
          </div>
          <div className={styles.form}>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>规则名称</span>
              <input
                className="input"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="例如：银行板块回撤预警"
              />
            </label>

            <label className={styles.field}>
              <span className={styles.fieldLabel}>服务标的</span>
              <select
                className="select"
                value={draftSymbol}
                onChange={(event) => {
                  const nextSymbol = normalizeAlertSymbol(event.target.value);
                  setDraftSymbol(nextSymbol);
                  onFocusSymbolChange?.(nextSymbol);
                }}
              >
                {normalizedSymbols.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>

            <label className={styles.field}>
              <span className={styles.fieldLabel}>提醒类型</span>
              <select
                className="select"
                value={ruleType}
                onChange={(event) => {
                  const nextType = event.target.value as AlertRuleType;
                  setRuleType(nextType);
                  setThreshold(buildAlertDefaultThreshold(nextType));
                }}
              >
                <option value="price">价格提醒</option>
                <option value="event">事件提醒</option>
                <option value="earnings">财报提醒</option>
              </select>
            </label>

            {ruleType === "price" ? (
              <>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>触发条件</span>
                  <select
                    className="select"
                    value={priceOperator}
                    onChange={(event) => setPriceOperator(event.target.value as AlertPriceOperator)}
                  >
                    <option value="gte">价格高于等于阈值</option>
                    <option value="lte">价格低于等于阈值</option>
                  </select>
                </label>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>阈值</span>
                  <input
                    className="input"
                    type="number"
                    min="0"
                    step="0.0001"
                    value={threshold}
                    onChange={(event) => setThreshold(event.target.value)}
                  />
                </label>
              </>
            ) : null}

            {ruleType === "event" ? (
              <label className={styles.field}>
                <span className={styles.fieldLabel}>事件类型</span>
                <input
                  className="input"
                  value={eventType}
                  onChange={(event) => setEventType(event.target.value)}
                  placeholder="buyback / earnings / insider"
                />
              </label>
            ) : null}

            {ruleType === "earnings" ? (
              <label className={styles.field}>
                <span className={styles.fieldLabel}>财报范围</span>
                <select
                  className="select"
                  value={researchKind}
                  onChange={(event) => setResearchKind(event.target.value as AlertResearchKind)}
                >
                  <option value="all">财报和盈利预测</option>
                  <option value="report">仅财报</option>
                  <option value="earning_forecast">仅盈利预测</option>
                </select>
              </label>
            ) : null}

            <label className={styles.field}>
              <span className={styles.fieldLabel}>回看天数</span>
              <input
                className="input"
                type="number"
                min={1}
                max={30}
                value={lookbackDays}
                onChange={(event) =>
                  setLookbackDays(Math.max(1, Math.min(30, Number(event.target.value) || DEFAULT_ALERT_LOOKBACK_DAYS)))
                }
              />
            </label>

            {actionError ? (
              <div className="helper" style={{ color: "var(--finance-rise)" }}>
                {actionError}
              </div>
            ) : null}

            <button type="button" className="primary-button" onClick={handleCreateRule}>
              创建规则
            </button>
          </div>
        </section>

        <section className="card market-panel">
          <div className="section-headline">
            <div>
              <div className="card-title">规则列表</div>
              <div className="helper">当前面板只展示属于这批标的的规则，并支持按单个标的进一步聚焦。</div>
            </div>
            <div className={styles.toolbar}>
              <label className={styles.field}>
                <span className={styles.fieldLabel}>查看范围</span>
                <select
                className="select"
                value={filterSymbol}
                onChange={(event) => {
                  const nextSymbol = normalizeAlertSymbol(event.target.value);
                  setFilterSymbol(nextSymbol);
                  if (nextSymbol) {
                    onFocusSymbolChange?.(nextSymbol);
                    }
                  }}
                >
                  <option value="">全部标的</option>
                  {normalizedSymbols.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
              </label>
              <button type="button" className="stock-page-button" onClick={() => centerQuery.refetch()}>
                刷新状态
              </button>
            </div>
          </div>

          {centerQuery.isLoading && scopedItems.length === 0 ? <div className="helper">告警规则加载中...</div> : null}
          {centerQuery.error ? (
            <div className="helper" style={{ color: "var(--finance-rise)" }}>
              {centerQuery.error.message}
            </div>
          ) : null}
          {!centerQuery.isLoading && !centerQuery.error && visibleItems.length === 0 ? (
            <div className="surface-empty">
              <strong>当前范围还没有规则</strong>
              <div className="helper">先为这批标的创建价格、事件或财报规则，再回到这里统一查看。</div>
            </div>
          ) : null}

          <div className={styles.rules}>
            {visibleItems.map((item) => (
              <div key={item.id} className={styles.ruleCard}>
                <div className={styles.ruleHead}>
                  <div>
                    <div style={{ fontWeight: 700 }}>{item.name}</div>
                    <div className="helper">{`${item.symbol} · ${item.rule_type} · ${buildAlertRuleSummary(item)}`}</div>
                  </div>
                  <div className={styles.ruleMeta}>
                    <span className={styles.statusChip} data-status={item.status}>
                      {item.status}
                    </span>
                    {!item.is_active ? <span className="kicker">Paused</span> : null}
                  </div>
                </div>

                <div className="helper">{item.status_message}</div>
                <div className="helper">{buildAlertReadableExplanation(item)}</div>
                {item.context_title ? <div style={{ fontSize: 13 }}>{item.context_title}</div> : null}
                {item.matched_at ? <div className="helper">{`命中时间：${item.matched_at}`}</div> : null}

                <div className={styles.actions}>
                  <button
                    type="button"
                    className="stock-page-button"
                    onClick={() => {
                      const nextSymbol = normalizeAlertSymbol(item.symbol);
                      setFilterSymbol(nextSymbol);
                      onFocusSymbolChange?.(nextSymbol);
                    }}
                  >
                    聚焦标的
                  </button>
                  <button
                    type="button"
                    className="stock-page-button"
                    onClick={() => handleToggleRule(item.id, item.is_active)}
                    disabled={busyRuleId === item.id}
                  >
                    {item.is_active ? "停用" : "启用"}
                  </button>
                  <button
                    type="button"
                    className="stock-page-button"
                    onClick={() => handleDeleteRule(item.id)}
                    disabled={busyRuleId === item.id}
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
