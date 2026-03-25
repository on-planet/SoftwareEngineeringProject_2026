import React, { useState } from "react";

import { useApiQuery } from "../../hooks/useApiQuery";
import { useAuth } from "../../providers/AuthProvider";
import {
  AlertPriceOperator,
  AlertResearchKind,
  AlertRuleType,
  createMyAlert,
  deleteMyAlert,
  getMyAlertCenter,
  updateMyAlert,
} from "../../services/api";

import styles from "./AlertsCenterPage.module.css";

const DEFAULT_LOOKBACK_DAYS = 7;

function buildDefaultThreshold(type: AlertRuleType) {
  return type === "price" ? "10" : "";
}

export function AlertsCenterPage() {
  const { isAuthenticated, isLoading: authLoading, token } = useAuth();
  const [ruleType, setRuleType] = useState<AlertRuleType>("price");
  const [name, setName] = useState("");
  const [symbol, setSymbol] = useState("");
  const [priceOperator, setPriceOperator] = useState<AlertPriceOperator>("gte");
  const [threshold, setThreshold] = useState(buildDefaultThreshold("price"));
  const [eventType, setEventType] = useState("buyback");
  const [researchKind, setResearchKind] = useState<AlertResearchKind>("all");
  const [lookbackDays, setLookbackDays] = useState(DEFAULT_LOOKBACK_DAYS);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyRuleId, setBusyRuleId] = useState<number | null>(null);

  const centerQuery = useApiQuery(
    isAuthenticated && token ? ["alerts-center", token] : null,
    () => getMyAlertCenter(token as string),
    {
      staleTimeMs: 30_000,
      cacheTimeMs: 5 * 60_000,
    },
  );

  const handleCreateRule = async () => {
    if (!token || !isAuthenticated) {
      setActionError("登录后才能创建告警规则。");
      return;
    }
    const normalizedName = name.trim();
    const normalizedSymbol = symbol.trim().toUpperCase();
    if (!normalizedName || !normalizedSymbol) {
      setActionError("请填写规则名称和股票代码。");
      return;
    }
    if (ruleType === "price" && (!threshold || Number(threshold) <= 0)) {
      setActionError("价格提醒需要填写大于 0 的阈值。");
      return;
    }
    if (ruleType === "event" && !eventType.trim()) {
      setActionError("事件提醒需要填写事件类型。");
      return;
    }
    try {
      await createMyAlert(token, {
        name: normalizedName,
        rule_type: ruleType,
        symbol: normalizedSymbol,
        price_operator: ruleType === "price" ? priceOperator : undefined,
        threshold: ruleType === "price" ? Number(threshold) : undefined,
        event_type: ruleType === "event" ? eventType.trim() : undefined,
        research_kind: ruleType === "earnings" ? researchKind : undefined,
        lookback_days: lookbackDays,
      });
      setName("");
      setSymbol("");
      setThreshold(buildDefaultThreshold(ruleType));
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
      await updateMyAlert(token, ruleId, { is_active: !current });
      await centerQuery.refetch();
      setActionError(null);
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
      await deleteMyAlert(token, ruleId);
      await centerQuery.refetch();
      setActionError(null);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "删除告警失败");
    } finally {
      setBusyRuleId(null);
    }
  };

  if (authLoading) {
    return (
      <div className="page">
        <section className="card market-panel">
          <div className="skeleton-stack">
            <span className="skeleton-line" data-width="short" />
            <div className="skeleton-card" />
          </div>
        </section>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="page">
        <section className="card market-panel">
          <div className="surface-empty">
            <strong>登录后查看告警中心</strong>
            <div className="helper">价格、事件和财报提醒都需要和你的个人账户绑定保存。</div>
          </div>
        </section>
      </div>
    );
  }

  const center = centerQuery.data;

  return (
    <div className="page">
      <section className={`card market-panel ${styles.hero}`}>
        <div>
          <span className="kicker">Alert Center</span>
          <h1 className="page-title">告警中心</h1>
          <p className="helper" style={{ marginTop: 8, maxWidth: 760 }}>
            先支持规则管理和即时状态评估，不做异步推送；价格、事件和财报提醒都基于当前数据库/行情快照实时计算。
          </p>
        </div>
        <div className={styles.heroMetrics}>
          <div className={styles.metric}>
            <div className="helper">规则总数</div>
            <div className={styles.metricValue}>{center?.total ?? 0}</div>
          </div>
          <div className={styles.metric}>
            <div className="helper">当前触发</div>
            <div className={styles.metricValue}>{center?.triggered ?? 0}</div>
          </div>
          <div className={styles.metric}>
            <div className="helper">规则类型</div>
            <div className={styles.metricValue}>3</div>
          </div>
        </div>
      </section>

      <section className={styles.layout}>
        <section className="card market-panel">
          <div className="card-title" style={{ marginBottom: 12 }}>
            新建规则
          </div>
          <div className={styles.form}>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>规则名称</span>
              <input className="input" value={name} onChange={(event) => setName(event.target.value)} placeholder="例如：平安银行跌破支撑位" />
            </label>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>股票代码</span>
              <input className="input" value={symbol} onChange={(event) => setSymbol(event.target.value)} placeholder="000001.SZ" />
            </label>
            <label className={styles.field}>
              <span className={styles.fieldLabel}>提醒类型</span>
              <select
                className="select"
                value={ruleType}
                onChange={(event) => {
                  const nextType = event.target.value as AlertRuleType;
                  setRuleType(nextType);
                  setThreshold(buildDefaultThreshold(nextType));
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
                  <select className="select" value={priceOperator} onChange={(event) => setPriceOperator(event.target.value as AlertPriceOperator)}>
                    <option value="gte">价格高于等于阈值</option>
                    <option value="lte">价格低于等于阈值</option>
                  </select>
                </label>
                <label className={styles.field}>
                  <span className={styles.fieldLabel}>阈值</span>
                  <input className="input" type="number" min="0" step="0.0001" value={threshold} onChange={(event) => setThreshold(event.target.value)} />
                </label>
              </>
            ) : null}
            {ruleType === "event" ? (
              <label className={styles.field}>
                <span className={styles.fieldLabel}>事件类型</span>
                <input className="input" value={eventType} onChange={(event) => setEventType(event.target.value)} placeholder="buyback / insider / earnings" />
              </label>
            ) : null}
            {ruleType === "earnings" ? (
              <label className={styles.field}>
                <span className={styles.fieldLabel}>财报范围</span>
                <select className="select" value={researchKind} onChange={(event) => setResearchKind(event.target.value as AlertResearchKind)}>
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
                onChange={(event) => setLookbackDays(Math.max(1, Math.min(30, Number(event.target.value) || DEFAULT_LOOKBACK_DAYS)))}
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
              <div className="helper">触发状态会按当前行情、事件和研报数据实时评估。</div>
            </div>
            <button type="button" className="stock-page-button" onClick={() => centerQuery.refetch()}>
              刷新状态
            </button>
          </div>

          {centerQuery.isLoading && !(center?.items || []).length ? <div className="helper">告警中心加载中...</div> : null}
          {centerQuery.error ? (
            <div className="helper" style={{ color: "var(--finance-rise)" }}>
              {centerQuery.error.message}
            </div>
          ) : null}
          {!centerQuery.isLoading && !centerQuery.error && !(center?.items || []).length ? (
            <div className="surface-empty">
              <strong>还没有任何规则</strong>
              <div className="helper">先在左侧创建价格、事件或财报提醒。</div>
            </div>
          ) : null}

          <div className={styles.rules}>
            {(center?.items || []).map((item) => (
              <div key={item.id} className={styles.ruleCard}>
                <div className={styles.ruleHead}>
                  <div>
                    <div style={{ fontWeight: 700 }}>{item.name}</div>
                    <div className="helper">{`${item.symbol} · ${item.rule_type}`}</div>
                  </div>
                  <div className={styles.ruleMeta}>
                    <span className={styles.statusChip} data-status={item.status}>
                      {item.status}
                    </span>
                    {!item.is_active ? <span className="kicker">Paused</span> : null}
                  </div>
                </div>
                <div className="helper">{item.status_message}</div>
                {item.context_title ? <div style={{ fontSize: 13 }}>{item.context_title}</div> : null}
                {item.matched_at ? <div className="helper">{`命中时间：${item.matched_at}`}</div> : null}
                <div className={styles.ruleActions}>
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
      </section>
    </div>
  );
}
