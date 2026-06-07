import React from "react";

type CigarbuttAnalysisResponse = {
  symbol: string;
  stock_price?: number | null;
  analysis: Record<string, unknown>;
};

type CigarbuttAnalysisPanelProps = {
  data: CigarbuttAnalysisResponse;
  compact?: boolean;
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

function formatNumber(value: unknown, digits = 2) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value.toFixed(digits);
  }
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  return String(value);
}

function formatPrice(value: unknown) {
  return formatNumber(value, 3);
}

function formatPercent(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? `${(value * 100).toFixed(1)}%` : "--";
}

function ratingTone(value: unknown): "positive" | "negative" | "neutral" {
  const text = String(value ?? "").toUpperCase();
  if (!text) {
    return "neutral";
  }
  if (text.includes("A") || text.includes("优") || text.includes("强")) {
    return "positive";
  }
  if (text.includes("C") || text.includes("D") || text.includes("弱") || text.includes("差") || text.includes("不")) {
    return "negative";
  }
  return "neutral";
}

function yesNoTone(value: unknown): "positive" | "negative" | "neutral" {
  if (value === true) {
    return "positive";
  }
  if (value === false) {
    return "negative";
  }
  return "neutral";
}

function StatusPill({ active, label }: { active: unknown; label: string }) {
  const passed = active === true;
  return (
    <span className="strategy-pill" data-tone={yesNoTone(active)}>
      {label}: {passed ? "通过" : "未通过"}
    </span>
  );
}

export function CigarbuttAnalysisPanel({ data, compact = false }: CigarbuttAnalysisPanelProps) {
  const analysis = asRecord(data.analysis);
  const subtypeA = asRecord(analysis.subtype_a);
  const subtypeB = asRecord(analysis.subtype_b);
  const subtypeC = asRecord(analysis.subtype_c);
  const redemption = asRecord(analysis.redemption_path);
  const tradePlan = asRecord(analysis.trade_plan);
  const entry = asRecord(tradePlan.entry);
  const stopLoss = asRecord(tradePlan.stop_loss);
  const takeProfit = asRecord(tradePlan.take_profit);
  const riskFlags = asStringArray(analysis.risk_flags);
  const factTone = ratingTone(analysis.fact_check_rating);
  const bonusTone = ratingTone(analysis.bonus_adjusted_rating);
  const navCards = [
    {
      label: "T0 清算价值",
      nav: analysis.t0_nav_per_share,
      ratio: analysis.t0_ratio,
      pass: analysis.is_t0_pass,
      detail: "现金、应收和存货折扣后的保守底线",
    },
    {
      label: "T1 营运资本",
      nav: analysis.t1_nav_per_share,
      ratio: analysis.t1_ratio,
      pass: analysis.is_t1_pass,
      detail: "加入营运资产后的中性安全边际",
    },
    {
      label: "T2 账面价值",
      nav: analysis.t2_nav_per_share,
      ratio: analysis.t2_ratio,
      pass: analysis.is_t2_pass,
      detail: "全部净资产口径下的宽松估值锚",
    },
  ];

  return (
    <div className="cigarbutt-panel">
      <div className="cigarbutt-hero">
        <div>
          <div className="card-title">静态价值型烟蒂股</div>
          <div className="helper">以清算价值、营运资本、账面价值和事实核查组合评估安全边际。</div>
        </div>
        <div className="cigarbutt-score-strip">
          <div className="cigarbutt-score">
            <span>股票</span>
            <strong>{data.symbol}</strong>
          </div>
          <div className="cigarbutt-score">
            <span>现价</span>
            <strong>{formatPrice(data.stock_price)}</strong>
          </div>
          <div className="cigarbutt-score">
            <span>最佳层级</span>
            <strong>{String(analysis.best_t_level ?? "--")}</strong>
          </div>
        </div>
      </div>

      <div className="cigarbutt-rating-grid">
        <div className="cigarbutt-rating-card">
          <span>Fact Check 评级</span>
          <strong data-tone={factTone}>{String(analysis.fact_check_rating ?? "--")}</strong>
        </div>
        <div className="cigarbutt-rating-card">
          <span>加分后评级</span>
          <strong data-tone={bonusTone}>{String(analysis.bonus_adjusted_rating ?? "--")}</strong>
        </div>
        <div className="cigarbutt-rating-card">
          <span>总加分</span>
          <strong>{formatNumber(analysis.total_bonus, 1)}</strong>
        </div>
      </div>

      <div className="cigarbutt-nav-grid">
        {navCards.map((item) => (
          <div key={item.label} className="cigarbutt-nav-card" data-pass={item.pass === true}>
            <div className="cigarbutt-nav-head">
              <span>{item.label}</span>
              <span className="strategy-pill" data-tone={yesNoTone(item.pass)}>
                {item.pass ? "通过" : "未通过"}
              </span>
            </div>
            <div className="cigarbutt-nav-values">
              <div>
                <span>NAV / 股</span>
                <strong>{formatPrice(item.nav)}</strong>
              </div>
              <div>
                <span>股价 / NAV</span>
                <strong>{formatNumber(item.ratio)}</strong>
              </div>
            </div>
            <div className="helper">{item.detail}</div>
          </div>
        ))}
      </div>

      <div className="cigarbutt-split">
        <div className="cigarbutt-block">
          <div className="card-title">子类型与兑现路径</div>
          <div className="strategy-pill-row">
            <StatusPill active={subtypeA.is_valid} label="高股息破净" />
            <StatusPill active={subtypeB.is_valid} label="控股套利" />
            <span className="strategy-pill" data-tone={subtypeC.subtype ? "positive" : "neutral"}>
              事件型: {String(subtypeC.subtype ?? "暂无")}
            </span>
            <StatusPill active={redemption.has_valid_path} label="兑现路径" />
          </div>
        </div>

        <div className="cigarbutt-block">
          <div className="card-title">交易计划</div>
          <div className="cigarbutt-plan-grid">
            <div>
              <span>目标仓位</span>
              <strong>{formatPercent(entry.target_position_ratio)}</strong>
            </div>
            <div>
              <span>首次买入</span>
              <strong>{formatPrice(entry.entry_price)}</strong>
            </div>
            <div>
              <span>硬止损</span>
              <strong>{formatPrice(stopLoss.hard_stop_price)}</strong>
            </div>
            <div>
              <span>T2 目标</span>
              <strong>{formatPrice(takeProfit.t2_target_price)}</strong>
            </div>
          </div>
        </div>
      </div>

      {!compact ? (
        <div className="cigarbutt-split">
          <div className="cigarbutt-block">
            <div className="card-title">建仓阶梯</div>
            <div className="cigarbutt-plan-grid">
              <div>
                <span>跌 10% 追加</span>
                <strong>{formatPrice(entry.add_10pct_price)}</strong>
              </div>
              <div>
                <span>跌 15% 满仓</span>
                <strong>{formatPrice(entry.add_15pct_price)}</strong>
              </div>
              <div>
                <span>T0 减仓</span>
                <strong>{formatPrice(takeProfit.t0_target_price)}</strong>
              </div>
              <div>
                <span>T1 减仓</span>
                <strong>{formatPrice(takeProfit.t1_target_price)}</strong>
              </div>
            </div>
          </div>
          <div className="cigarbutt-block" data-risk={riskFlags.length > 0}>
            <div className="card-title">风险标记</div>
            {riskFlags.length > 0 ? (
              <ul className="cigarbutt-risk-list">
                {riskFlags.map((flag) => (
                  <li key={flag}>{flag}</li>
                ))}
              </ul>
            ) : (
              <div className="helper">暂无高优先级风险标记。</div>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}
