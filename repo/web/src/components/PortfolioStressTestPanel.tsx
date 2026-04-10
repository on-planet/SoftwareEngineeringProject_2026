import React, { useEffect, useMemo, useRef, useState } from "react";

import ReactECharts from "echarts-for-react";

import {
  PORTFOLIO_SCENARIO_LAB_PRESETS,
  PORTFOLIO_STRESS_POSITION_LIMIT,
  buildPortfolioStressQueryKey,
  getPortfolioStressQueryOptions,
  loadPortfolioStress,
  normalizeScenarioLabInput,
  previewPortfolioStress,
  runPortfolioScenarioLab,
  validatePortfolioStressDraft,
  validateScenarioLabInput,
} from "../domain/portfolioStress";
import type { PortfolioTargetScope } from "../domain/portfolioDiagnostics";
import { useApiQuery } from "../hooks/useApiQuery";
import { useAuth } from "../providers/AuthProvider";
import {
  PortfolioScenarioImpact,
  PortfolioScenarioLabResponse,
  PortfolioStressResponse,
  PortfolioStressRuleScope,
  PortfolioStressScenario,
} from "../services/api";
import { formatPercent } from "../utils/format";

type CustomRuleForm = {
  id: string;
  scopeType: PortfolioStressRuleScope;
  scopeValue: string;
  shockPctText: string;
};

const textareaStyle: React.CSSProperties = {
  width: "100%",
  minHeight: 96,
  resize: "vertical",
  padding: "12px 14px",
  borderRadius: 14,
  border: "1px solid var(--border)",
  background: "#ffffff",
  color: "var(--text)",
  font: "inherit",
};

function formatMoney(value?: number | null, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return Number(value).toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function formatSignedMoney(value?: number | null, digits = 0) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatMoney(value, digits)}`;
}

function formatSignedPercent(value?: number | null, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  const sign = value > 0 ? "+" : "";
  return `${sign}${formatPercent(value, digits)}`;
}

function changeTone(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "neutral";
  }
  if (value < 0) {
    return "negative";
  }
  if (value > 0) {
    return "positive";
  }
  return "neutral";
}

function buildEmptyRule(id: string): CustomRuleForm {
  return {
    id,
    scopeType: "sector",
    scopeValue: "",
    shockPctText: "-5",
  };
}

function buildScenarioLossOption(scenarios: PortfolioStressScenario[]) {
  if (!scenarios.length) {
    return null;
  }
  return {
    color: ["#b42318"],
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (value: number) => formatPercent(value, 2),
    },
    grid: { left: 52, right: 20, top: 24, bottom: 44 },
    xAxis: {
      type: "category",
      data: scenarios.map((item) => item.name),
      axisLabel: { interval: 0, rotate: 10 },
    },
    yAxis: {
      type: "value",
      axisLabel: {
        formatter: (value: number) => `${(value * 100).toFixed(0)}%`,
      },
    },
    series: [
      {
        type: "bar",
        barMaxWidth: 42,
        data: scenarios.map((item) => item.loss_pct),
        itemStyle: { borderRadius: [10, 10, 0, 0] },
      },
    ],
  };
}

function buildImpactOption(items: Array<{ label: string; value_change: number }>, color: string) {
  if (!items.length) {
    return null;
  }
  return {
    color: [color],
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      valueFormatter: (value: number) => formatSignedMoney(value, 0),
    },
    grid: { left: 52, right: 20, top: 24, bottom: 36 },
    xAxis: {
      type: "value",
      axisLabel: {
        formatter: (value: number) => formatMoney(value, 0),
      },
    },
    yAxis: {
      type: "category",
      data: items.map((item) => item.label),
    },
    series: [
      {
        type: "bar",
        barMaxWidth: 24,
        data: items.map((item) => item.value_change),
      },
    ],
  };
}

function renderImpactCards(title: string, items: PortfolioScenarioImpact[], emptyText: string) {
  return (
    <div className="depth-card">
      <div className="card-title">{title}</div>
      <div style={{ display: "grid", gap: 10, marginTop: 12 }}>
        {items.length === 0 ? (
          <div className="helper">{emptyText}</div>
        ) : (
          items.map((item) => (
            <div
              key={`${title}-${item.label}`}
              style={{
                border: "1px solid rgba(15, 23, 42, 0.08)",
                borderRadius: 14,
                padding: 12,
                background: "rgba(255, 255, 255, 0.82)",
              }}
            >
              <div style={{ fontWeight: 700 }}>{item.label}</div>
              <div className="helper" style={{ marginTop: 6 }}>
                {item.rationale}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

function previewLabel(item: PortfolioStressScenario) {
  if (item.code === "scenario_lab_preview") {
    return `实验室 · ${item.name}`;
  }
  if (item.code === "custom_preview") {
    return `自定义 · ${item.name}`;
  }
  return item.name;
}

function formatConfidence(value?: string | null) {
  if (!value) {
    return "--";
  }
  if (value === "high") {
    return "高";
  }
  if (value === "medium") {
    return "中";
  }
  if (value === "low") {
    return "低";
  }
  return value;
}

function formatParserLabel(value?: string | null) {
  if (value === "template") {
    return "模板映射";
  }
  if (value === "generic") {
    return "通用范围解析";
  }
  if (value === "unparsed") {
    return "待人工确认";
  }
  return value || "--";
}

function formatClauseMagnitude(shockPct?: number | null, extractedBp?: number | null) {
  if (extractedBp !== undefined && extractedBp !== null) {
    return `${Math.round(extractedBp)}bp`;
  }
  if (shockPct !== undefined && shockPct !== null) {
    return formatPercent(shockPct, 0);
  }
  return null;
}

function summarizeMatchedTemplates(parse: PortfolioScenarioLabResponse["parse"]) {
  if (parse.matched_template_names.length) {
    return parse.matched_template_names.join(" + ");
  }
  if (parse.matched_template_name) {
    return parse.matched_template_name;
  }
  return "generic scope parser";
}

const PORTFOLIO_SCENARIO_LAB_QUICK_INPUTS = [
  "油价上涨25%",
  "人民币贬值3%",
  "地产政策放松",
  "美债收益率上行50bp",
  "港股科技下跌8%",
];

type PortfolioStressTestPanelProps = {
  targetType?: PortfolioTargetScope;
};

type StressComposerMode = "lab" | "custom";

export function PortfolioStressTestPanel({
  targetType = "bought",
}: PortfolioStressTestPanelProps) {
  const { token, isAuthenticated } = useAuth();
  const isWatch = targetType === "watch";
  const scopeLabel = isWatch ? "观察标的" : "已买组合";
  const basketHint = isWatch ? "当前按等权观察篮子估算，不代表真实持仓金额。" : "当前按已买持仓金额和权重估算。";
  const nextRuleIdRef = useRef(1);
  const [selectedLabPresetId, setSelectedLabPresetId] = useState(PORTFOLIO_SCENARIO_LAB_PRESETS[0]?.id ?? "");
  const [labInput, setLabInput] = useState(PORTFOLIO_SCENARIO_LAB_PRESETS[0]?.prompt ?? "");
  const [labResult, setLabResult] = useState<PortfolioScenarioLabResponse | null>(null);
  const [labLoading, setLabLoading] = useState(false);
  const [labError, setLabError] = useState<string | null>(null);
  const [customName, setCustomName] = useState("自定义场景");
  const [customDescription, setCustomDescription] = useState("");
  const [customRules, setCustomRules] = useState<CustomRuleForm[]>([buildEmptyRule("rule-1")]);
  const [customScenario, setCustomScenario] = useState<PortfolioStressScenario | null>(null);
  const [customLoading, setCustomLoading] = useState(false);
  const [customError, setCustomError] = useState<string | null>(null);
  const [selectedCode, setSelectedCode] = useState<string>("");
  const [composerMode, setComposerMode] = useState<StressComposerMode>("lab");

  const stressQuery = useApiQuery<PortfolioStressResponse>(
    isAuthenticated && token ? buildPortfolioStressQueryKey(token, targetType, PORTFOLIO_STRESS_POSITION_LIMIT) : null,
    () => loadPortfolioStress(token || "", targetType, PORTFOLIO_STRESS_POSITION_LIMIT),
    getPortfolioStressQueryOptions(targetType),
  );

  const payload = stressQuery.data;
  const presetScenarios = payload?.scenarios ?? [];
  const scenarios = useMemo(() => {
    const previews: PortfolioStressScenario[] = [];
    if (labResult?.scenario) {
      previews.push(labResult.scenario);
    }
    if (customScenario) {
      previews.push(customScenario);
    }
    return [...previews, ...presetScenarios];
  }, [customScenario, labResult, presetScenarios]);

  useEffect(() => {
    setLabResult(null);
    setLabError(null);
    setCustomScenario(null);
    setCustomError(null);
    setSelectedCode("");
    setComposerMode("lab");
  }, [targetType]);

  useEffect(() => {
    if (!scenarios.length) {
      setSelectedCode("");
      return;
    }
    const worst = payload?.summary.worst_scenario_code;
    setSelectedCode((current) => {
      if (current && scenarios.some((item) => item.code === current)) {
        return current;
      }
      if (labResult?.scenario) {
        return labResult.scenario.code;
      }
      if (customScenario) {
        return customScenario.code;
      }
      return worst && scenarios.some((item) => item.code === worst) ? worst : scenarios[0].code;
    });
  }, [customScenario, labResult, payload?.summary.worst_scenario_code, scenarios]);

  const selectedScenario = useMemo(
    () => scenarios.find((item) => item.code === selectedCode) ?? scenarios[0] ?? null,
    [scenarios, selectedCode],
  );

  const lossOption = useMemo(() => buildScenarioLossOption(scenarios), [scenarios]);
  const sectorImpactOption = useMemo(
    () =>
      selectedScenario
        ? buildImpactOption(
            selectedScenario.sector_impacts.slice(0, 6).map((item) => ({
              label: item.label,
              value_change: item.value_change,
            })),
            "#2563eb",
          )
        : null,
    [selectedScenario],
  );
  const marketImpactOption = useMemo(
    () =>
      selectedScenario
        ? buildImpactOption(
            selectedScenario.market_impacts.map((item) => ({
              label: item.label,
              value_change: item.value_change,
            })),
            "#f79009",
          )
        : null,
    [selectedScenario],
  );

  const handleRuleChange = (ruleId: string, patch: Partial<CustomRuleForm>) => {
    setCustomRules((prev) =>
      prev.map((item) => {
        if (item.id !== ruleId) {
          return item;
        }
        const next = { ...item, ...patch };
        if (patch.scopeType === "all") {
          next.scopeValue = "";
        }
        return next;
      }),
    );
  };

  const handleAddRule = () => {
    nextRuleIdRef.current += 1;
    setCustomRules((prev) => [...prev, buildEmptyRule(`rule-${nextRuleIdRef.current}`)]);
  };

  const handleRemoveRule = (ruleId: string) => {
    setCustomRules((prev) => (prev.length <= 1 ? prev : prev.filter((item) => item.id !== ruleId)));
  };

  const handleRunScenarioLab = async () => {
    if (!token) {
      return;
    }
    const normalized = normalizeScenarioLabInput(labInput);
    const errorText = validateScenarioLabInput(normalized);
    if (errorText) {
      setLabError(errorText);
      return;
    }
    setLabLoading(true);
    setLabError(null);
    try {
      const result = await runPortfolioScenarioLab(token, targetType, normalized, PORTFOLIO_STRESS_POSITION_LIMIT);
      setLabResult(result);
      setSelectedCode(result.scenario.code);
    } catch (error) {
      setLabError(error instanceof Error ? error.message : "情景实验室解析失败");
    } finally {
      setLabLoading(false);
    }
  };

  const applyLabPreset = (presetId: string) => {
    const matched = PORTFOLIO_SCENARIO_LAB_PRESETS.find((item) => item.id === presetId);
    if (!matched) {
      return;
    }
    setSelectedLabPresetId(matched.id);
    setLabInput(matched.prompt);
    setLabError(null);
  };

  const handlePreviewCustomScenario = async () => {
    if (!token) {
      return;
    }
    const draftError = validatePortfolioStressDraft(customName, customRules);
    if (draftError) {
      setCustomError(draftError);
      return;
    }

    const parsedRules = [];
    for (const rule of customRules) {
      const shockPct = Number(rule.shockPctText);
      if (!Number.isFinite(shockPct)) {
        setCustomError("冲击值必须是有效数字。");
        return;
      }
      if (shockPct < -95 || shockPct > 95) {
        setCustomError("冲击值必须在 -95 到 95 之间。");
        return;
      }
      const scopeValue = rule.scopeType === "all" ? null : rule.scopeValue.trim();
      if (rule.scopeType !== "all" && !scopeValue) {
        setCustomError("市场、行业和个股规则需要填写范围值。");
        return;
      }
      parsedRules.push({
        scope_type: rule.scopeType,
        scope_value: scopeValue,
        shock_pct: shockPct / 100,
      });
    }

    setCustomLoading(true);
    setCustomError(null);
    try {
      const result = await previewPortfolioStress(token, targetType, {
        name: customName.trim(),
        description: customDescription.trim(),
        position_limit: PORTFOLIO_STRESS_POSITION_LIMIT,
        rules: parsedRules,
      });
      setCustomScenario(result);
      setSelectedCode(result.code);
    } catch (error) {
      setCustomError(error instanceof Error ? error.message : "自定义场景预览失败");
    } finally {
      setCustomLoading(false);
    }
  };

  if (!isAuthenticated || !token) {
    return null;
  }

  if (stressQuery.isLoading && !payload) {
    return <div className="helper">{`${scopeLabel}压力测试加载中...`}</div>;
  }

  if (stressQuery.error) {
    return <div className="helper">{`${scopeLabel}压力测试加载失败：${stressQuery.error.message}`}</div>;
  }

  if (!payload || payload.summary.holdings_count === 0) {
    return (
      <div className="surface-empty">
        <strong>{isWatch ? "暂无观察标的压力测试结果" : "暂无持仓压力测试结果"}</strong>
        <div className="helper">
          {isWatch ? "先添加至少一个观察标的，系统会按等权观察篮子生成情景模拟。" : "先录入至少一笔已买标的，系统才会生成情景模拟。"}
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <section className="strategy-feature-card">
        <div className="page-header" style={{ marginBottom: 12 }}>
          <div>
            <div className="card-title">情景实验室</div>
            <div className="helper">
              {composerMode === "lab"
                ? `直接输入一句自然语言，比如“油价上涨25%”或“人民币贬值3%”，系统会自动映射到${scopeLabel}压力测试和行业受益受损链路。`
                : `支持按全${isWatch ? "观察篮子" : "组合"}、市场、行业或单只股票叠加冲击，系统会即时回算损益。`}
            </div>
          </div>
          {composerMode === "lab" && labResult ? (
            <button type="button" className="stock-page-button" onClick={() => setLabResult(null)}>
              清除实验室结果
            </button>
          ) : null}
          {composerMode === "custom" && customScenario ? (
            <button type="button" className="stock-page-button" onClick={() => setCustomScenario(null)}>
              清除自定义结果
            </button>
          ) : null}
        </div>

        <div className="toolbar" style={{ marginBottom: 12 }}>
          <button
            type="button"
            className="stock-page-button"
            data-active={composerMode === "lab"}
            onClick={() => setComposerMode("lab")}
          >
            自然语言
          </button>
          <button
            type="button"
            className="stock-page-button"
            data-active={composerMode === "custom"}
            onClick={() => setComposerMode("custom")}
          >
            规则编辑
          </button>
        </div>

        {composerMode === "lab" ? (
          <>
            <textarea
              style={textareaStyle}
              value={labInput}
              onChange={(event) => {
                const nextValue = event.target.value;
                setLabInput(nextValue);
                const matchedPreset = PORTFOLIO_SCENARIO_LAB_PRESETS.find((item) => item.prompt === nextValue.trim());
                setSelectedLabPresetId(matchedPreset?.id ?? "");
              }}
              placeholder="例如：油价涨 8%，人民币贬值，地产政策放松，美债收益率上行 50bp"
            />

            <div className="helper" style={{ marginTop: 10 }}>
              {basketHint}
            </div>

            <div className="toolbar" style={{ marginTop: 12, alignItems: "center" }}>
              <button
                type="button"
                className="primary-button"
                onClick={() => void handleRunScenarioLab()}
                disabled={labLoading}
              >
                {labLoading ? "解析中..." : "运行情景实验室"}
              </button>
              {labInput.trim() ? (
                <button
                  type="button"
                  className="stock-page-button"
                  onClick={() => {
                    setLabInput("");
                    setSelectedLabPresetId("");
                    setLabError(null);
                  }}
                >
                  清空输入
                </button>
              ) : null}
            </div>

            <div style={{ marginTop: 12, display: "grid", gap: 10 }}>
              <div className="helper">快捷填充</div>
              <div className="strategy-pill-row" style={{ marginTop: 0 }}>
                {PORTFOLIO_SCENARIO_LAB_QUICK_INPUTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    className="stock-page-button"
                    onClick={() => {
                      setLabInput(prompt);
                      setSelectedLabPresetId("");
                      setLabError(null);
                    }}
                  >
                    {prompt}
                  </button>
                ))}
                {PORTFOLIO_SCENARIO_LAB_PRESETS.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    className="stock-page-button"
                    data-active={selectedLabPresetId === item.id}
                    onClick={() => applyLabPreset(item.id)}
                  >
                    {item.title}
                  </button>
                ))}
              </div>
            </div>

            {labError ? (
              <div className="helper" style={{ marginTop: 10, color: "#b42318" }}>
                {labError}
              </div>
            ) : null}

            {labResult ? (
              <>
                <div className="hero-grid" style={{ marginTop: 16 }}>
                  <div className="summary-card">
                    <div className="card-title">解析结果</div>
                    <div className="stock-score-value" style={{ fontSize: 22 }}>
                      {labResult.parse.headline}
                    </div>
                    <div className="helper">{summarizeMatchedTemplates(labResult.parse)}</div>
                  </div>
                  <div className="summary-card">
                    <div className="card-title">解析置信度</div>
                    <div className="stock-score-value">{formatConfidence(labResult.parse.confidence)}</div>
                    <div className="helper">
                      {labResult.parse.extracted_shock_pct !== undefined && labResult.parse.extracted_shock_pct !== null
                        ? `识别到冲击 ${formatPercent(labResult.parse.extracted_shock_pct, 0)}`
                        : "未显式提取百分比，采用模板默认冲击"}
                    </div>
                  </div>
                  <div className="summary-card">
                    <div className="card-title">组合变化</div>
                    <div
                      className="stock-score-value"
                      style={{ color: (labResult.scenario.portfolio_change || 0) < 0 ? "#b42318" : "#027a48" }}
                    >
                      {formatSignedMoney(labResult.scenario.portfolio_change, 0)}
                    </div>
                    <div className="helper">{formatSignedPercent(labResult.scenario.portfolio_change_pct, 2)}</div>
                  </div>
                  <div className="summary-card">
                    <div className="card-title">受影响权重</div>
                    <div className="stock-score-value">{formatPercent(labResult.scenario.impacted_weight, 0)}</div>
                    <div className="helper">命中规则的持仓占比</div>
                  </div>
                </div>

                <div
                  style={{
                    marginTop: 12,
                    border: "1px solid rgba(15, 23, 42, 0.08)",
                    borderRadius: 16,
                    padding: 14,
                    background: "rgba(255, 255, 255, 0.82)",
                  }}
                >
                  <div className="card-title">解释层</div>
                  <div className="helper" style={{ marginTop: 8 }}>
                    {labResult.parse.explanation}
                  </div>
                </div>

                {labResult.parse.matched_template_names.length ? (
                  <div
                    style={{
                      marginTop: 12,
                      border: "1px solid rgba(15, 23, 42, 0.08)",
                      borderRadius: 16,
                      padding: 14,
                      background: "rgba(255, 255, 255, 0.82)",
                    }}
                  >
                    <div className="card-title">命中模板</div>
                    <div className="strategy-pill-row" style={{ marginTop: 10 }}>
                      {labResult.parse.matched_template_names.map((item) => (
                        <span key={item} className="strategy-pill" data-tone="neutral">
                          {item}
                        </span>
                      ))}
                    </div>
                  </div>
                ) : null}

                {labResult.parse.clauses.length ? (
                  <div
                    style={{
                      marginTop: 12,
                      border: "1px solid rgba(15, 23, 42, 0.08)",
                      borderRadius: 16,
                      padding: 14,
                      background: "rgba(255, 255, 255, 0.82)",
                    }}
                  >
                    <div className="card-title">解析轨迹</div>
                    <div style={{ display: "grid", gap: 12, marginTop: 12 }}>
                      {labResult.parse.clauses.map((clause, index) => {
                        const magnitude = formatClauseMagnitude(clause.extracted_shock_pct, clause.extracted_bp);
                        return (
                          <div
                            key={`${clause.text}-${index}`}
                            style={{
                              border: "1px solid rgba(15, 23, 42, 0.08)",
                              borderRadius: 14,
                              padding: 12,
                              background: "rgba(255, 255, 255, 0.78)",
                            }}
                          >
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                gap: 12,
                                alignItems: "baseline",
                                flexWrap: "wrap",
                              }}
                            >
                              <div style={{ fontWeight: 700 }}>{clause.headline}</div>
                              <div className="helper">
                                {formatParserLabel(clause.parser)} · {formatConfidence(clause.confidence)}
                              </div>
                            </div>
                            <div className="helper" style={{ marginTop: 6 }}>
                              原始子句：{clause.text}
                            </div>
                            <div className="strategy-pill-row" style={{ marginTop: 10 }}>
                              {clause.matched_template_name ? (
                                <span className="strategy-pill" data-tone="neutral">
                                  模板：{clause.matched_template_name}
                                </span>
                              ) : null}
                              {magnitude ? (
                                <span className="strategy-pill" data-tone="neutral">
                                  冲击：{magnitude}
                                </span>
                              ) : null}
                              {clause.rules.length === 0 ? (
                                <span className="strategy-pill" data-tone="negative">
                                  未映射到规则
                                </span>
                              ) : null}
                              {clause.rules.map((rule) => (
                                <span key={`${clause.text}-${rule}`} className="strategy-pill" data-tone="neutral">
                                  {rule}
                                </span>
                              ))}
                            </div>
                            <div className="helper" style={{ marginTop: 10 }}>
                              {clause.explanation}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ) : null}

                <div className="depth-grid" style={{ marginTop: 16 }}>
                  {renderImpactCards("受益行业", labResult.beneficiaries, "当前模板没有显式标出受益行业。")}
                  {renderImpactCards("受损行业", labResult.losers, "当前模板没有显式标出受损行业。")}
                </div>
              </>
            ) : null}
          </>
        ) : (
          <>
            <div className="toolbar">
              <input
                className="input"
                type="text"
                value={customName}
                onChange={(event) => setCustomName(event.target.value)}
                placeholder="场景名称"
              />
              <input
                className="input"
                type="text"
                value={customDescription}
                onChange={(event) => setCustomDescription(event.target.value)}
                placeholder="场景说明，可选"
              />
            </div>

            <div style={{ display: "grid", gap: 10, marginTop: 14 }}>
              {customRules.map((rule, index) => (
                <div
                  key={rule.id}
                  style={{
                    display: "grid",
                    gridTemplateColumns: "120px minmax(180px, 1fr) 140px 88px",
                    gap: 10,
                    alignItems: "center",
                  }}
                >
                  <select
                    className="select"
                    value={rule.scopeType}
                    onChange={(event) => handleRuleChange(rule.id, { scopeType: event.target.value as PortfolioStressRuleScope })}
                  >
                    <option value="all">全组合</option>
                    <option value="market">市场</option>
                    <option value="sector">行业</option>
                    <option value="symbol">股票</option>
                  </select>
                  <input
                    className="input"
                    type="text"
                    value={rule.scopeValue}
                    disabled={rule.scopeType === "all"}
                    onChange={(event) => handleRuleChange(rule.id, { scopeValue: event.target.value })}
                    placeholder={
                      rule.scopeType === "market"
                        ? "A / HK / US"
                        : rule.scopeType === "sector"
                          ? "例如：科技、金融、房地产"
                          : rule.scopeType === "symbol"
                            ? "例如：00700.HK"
                            : "全组合无需填写"
                    }
                  />
                  <input
                    className="input"
                    type="number"
                    step="0.1"
                    min={-95}
                    max={95}
                    value={rule.shockPctText}
                    onChange={(event) => handleRuleChange(rule.id, { shockPctText: event.target.value })}
                    placeholder="冲击幅度%"
                  />
                  <button
                    type="button"
                    className="stock-page-button"
                    onClick={() => handleRemoveRule(rule.id)}
                    disabled={customRules.length <= 1}
                  >
                    {index === 0 ? "删规则" : "删除"}
                  </button>
                </div>
              ))}
            </div>

            <div className="toolbar" style={{ marginTop: 14 }}>
              <button type="button" className="stock-page-button" onClick={handleAddRule}>
                添加规则
              </button>
              <button
                type="button"
                className="primary-button"
                onClick={() => void handlePreviewCustomScenario()}
                disabled={customLoading}
              >
                {customLoading ? "计算中..." : "预览自定义场景"}
              </button>
            </div>

            <div className="helper" style={{ marginTop: 10 }}>
              规则会按命中结果叠加，并在单只股票层面限制到 ±95%。例如 `市场=HK -3%` 和 `行业=科技 -2%` 同时命中时，港股科技仓位按 `-5%` 处理。
            </div>
            {customError ? (
              <div className="helper" style={{ marginTop: 8, color: "#b42318" }}>
                {customError}
              </div>
            ) : null}
          </>
        )}
      </section>

      <div className="hero-grid">
        <div className="summary-card">
          <div className="card-title">当前组合市值</div>
          <div className="stock-score-value">{formatMoney(payload.summary.total_value, 0)}</div>
          <div className="helper">
            {payload.summary.as_of
              ? `价格日期 ${new Date(payload.summary.as_of).toLocaleDateString("zh-CN")}`
              : "基于最新价格估算"}
          </div>
        </div>
        <div className="summary-card">
          <div className="card-title">最坏预设场景</div>
          <div className="stock-score-value" style={{ fontSize: 24 }}>{payload.summary.worst_scenario_name ?? "--"}</div>
          <div className="helper">{payload.summary.scenario_count} 个预设场景</div>
        </div>
        <div className="summary-card">
          <div className="card-title">最大预估损失</div>
          <div className="stock-score-value" style={{ color: "#b42318" }}>
            {formatMoney(payload.summary.worst_loss_amount, 0)}
          </div>
          <div className="helper">{formatPercent(payload.summary.worst_loss_pct, 2)}</div>
        </div>
        <div className="summary-card">
          <div className="card-title">最大受影响权重</div>
          <div className="stock-score-value">{formatPercent(payload.summary.max_impacted_weight, 0)}</div>
          <div className="helper">单一场景命中的组合占比</div>
        </div>
      </div>

      <div style={{ display: "grid", gap: 8, marginTop: 0 }}>
        <div className="helper">已生成的场景结果</div>
        <div className="strategy-pill-row" style={{ marginTop: 0 }}>
        {scenarios.map((scenario) => (
          <button
            key={scenario.code}
            type="button"
            className="stock-page-button"
            data-active={selectedScenario?.code === scenario.code}
            onClick={() => setSelectedCode(scenario.code)}
          >
            {previewLabel(scenario)}
          </button>
        ))}
        </div>
      </div>

      {selectedScenario ? (
        <div className="strategy-feature-card">
          <div className="page-header" style={{ marginBottom: 12 }}>
            <div>
              <div className="card-title">{selectedScenario.name}</div>
              <div className="helper">{selectedScenario.description}</div>
            </div>
            <span className="strategy-pill" data-tone={changeTone(selectedScenario.portfolio_change)}>
              组合变化 {formatSignedPercent(selectedScenario.portfolio_change_pct, 2)}
            </span>
          </div>

          <div className="strategy-pill-row" style={{ marginTop: 0 }}>
            {selectedScenario.rules.map((rule) => (
              <span key={rule} className="strategy-pill" data-tone="neutral">
                {rule}
              </span>
            ))}
          </div>

          <div className="hero-grid" style={{ marginTop: 16 }}>
            <div className="summary-card">
              <div className="card-title">压力后组合市值</div>
              <div className="stock-score-value">{formatMoney(selectedScenario.projected_value, 0)}</div>
              <div className="helper">相对当前市值的模拟结果</div>
            </div>
            <div className="summary-card">
              <div className="card-title">组合损益变化</div>
              <div
                className="stock-score-value"
                style={{ color: selectedScenario.portfolio_change < 0 ? "#b42318" : "#027a48" }}
              >
                {formatSignedMoney(selectedScenario.portfolio_change, 0)}
              </div>
              <div className="helper">{formatSignedPercent(selectedScenario.portfolio_change_pct, 2)}</div>
            </div>
            <div className="summary-card">
              <div className="card-title">受影响权重</div>
              <div className="stock-score-value">{formatPercent(selectedScenario.impacted_weight, 0)}</div>
              <div className="helper">命中场景规则的持仓占比</div>
            </div>
            <div className="summary-card">
              <div className="card-title">平均冲击幅度</div>
              <div className="stock-score-value">{formatSignedPercent(selectedScenario.average_shock_pct, 2)}</div>
              <div className="helper">按受影响市值加权</div>
            </div>
          </div>
        </div>
      ) : null}

      <div className="depth-grid" style={{ marginTop: 0 }}>
        <div className="depth-card">
          <div className="card-title">场景损失对比</div>
          {lossOption ? (
            <ReactECharts option={lossOption} style={{ height: 280 }} />
          ) : (
            <div className="helper">暂无场景数据</div>
          )}
        </div>
        <div className="depth-card">
          <div className="card-title">行业冲击拆解</div>
          {sectorImpactOption ? (
            <ReactECharts option={sectorImpactOption} style={{ height: 280 }} />
          ) : (
            <div className="helper">暂无行业拆解</div>
          )}
        </div>
      </div>

      <div className="depth-grid" style={{ marginTop: 0 }}>
        <div className="depth-card">
          <div className="card-title">市场冲击拆解</div>
          {marketImpactOption ? (
            <ReactECharts option={marketImpactOption} style={{ height: 240 }} />
          ) : (
            <div className="helper">暂无市场拆解</div>
          )}
        </div>
        <div className="depth-card">
          <div className="card-title">受影响市值</div>
          <div className="stock-score-value">{selectedScenario ? formatMoney(selectedScenario.impacted_value, 0) : "--"}</div>
          <div className="helper">
            {selectedScenario
              ? `${selectedScenario.affected_positions.length} 个重点仓位被纳入明细展示`
              : "选择场景后查看"}
          </div>
        </div>
      </div>

      {selectedScenario ? (
        <section className="card">
          <div className="card-title">受影响仓位明细</div>
          <div style={{ overflowX: "auto", marginTop: 12 }}>
            <table className="data-table dense-table">
              <thead>
                <tr>
                  <th>股票</th>
                  <th>市场</th>
                  <th>行业</th>
                  <th>当前市值</th>
                  <th>组合权重</th>
                  <th>冲击幅度</th>
                  <th>压力后市值</th>
                  <th>价值变化</th>
                </tr>
              </thead>
              <tbody>
                {selectedScenario.affected_positions.map((item) => (
                  <tr key={`${selectedScenario.code}-${item.symbol}`}>
                    <td>{`${item.symbol} ${item.name}`}</td>
                    <td>{item.market || "--"}</td>
                    <td>{item.sector || "--"}</td>
                    <td>{formatMoney(item.current_value, 0)}</td>
                    <td>{formatPercent(item.weight, 2)}</td>
                    <td>{formatSignedPercent(item.shock_pct, 2)}</td>
                    <td>{formatMoney(item.projected_value, 0)}</td>
                    <td style={{ color: item.value_change < 0 ? "#b42318" : "#027a48" }}>
                      {formatSignedMoney(item.value_change, 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}
