from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.portfolio_stress import PortfolioScenarioLabIn, PortfolioScenarioLabOut
from app.services.portfolio_macro_scenarios import resolve_portfolio_macro_scenario
from app.services.portfolio_stress_service import (
    custom_rule_label,
    evaluate_custom_bought_target_stress_scenario,
    evaluate_custom_watch_target_stress_scenario,
)


def _factor_overrides_from_resolved(resolved) -> dict[str, object]:
    overrides: dict[str, object] = {}
    market_shock = 0.0
    rate_shock = 0.0
    fx_shock = 0.0
    commodity_shock = 0.0

    for clause in resolved.clauses:
        code = str(clause.matched_template_code or "").strip()
        if not code:
            continue
        if code == "oil_up":
            commodity_shock += float(clause.extracted_shock_pct or 0.08)
        elif code == "oil_down":
            commodity_shock -= float(clause.extracted_shock_pct or 0.08)
        elif code == "rmb_depreciation":
            fx_shock += float(clause.extracted_shock_pct or 0.03)
        elif code == "rmb_appreciation":
            fx_shock -= float(clause.extracted_shock_pct or 0.03)
        elif code == "rate_up":
            rate_shock += float((clause.extracted_bp or 50.0) / 10000.0)
        elif code == "rate_down":
            rate_shock -= float((clause.extracted_bp or 50.0) / 10000.0)
        elif code in {"export_recovery", "consumption_recovery", "tech_reg_easing", "property_easing"}:
            market_shock += float(clause.extracted_shock_pct or 0.02)
        elif code in {"export_slowdown", "consumption_weakness", "tech_reg_tightening", "property_tightening"}:
            market_shock -= float(clause.extracted_shock_pct or 0.02)

    if abs(market_shock) > 1e-9:
        overrides["market_shock"] = market_shock
    if abs(rate_shock) > 1e-9:
        overrides["rate_shock"] = rate_shock
    if abs(fx_shock) > 1e-9:
        overrides["fx_shock"] = fx_shock
    if abs(commodity_shock) > 1e-9:
        overrides["commodity_shock"] = commodity_shock

    confidence = str(resolved.confidence or "").lower()
    overrides["propagation_lambda"] = 0.26 if confidence == "high" else 0.20 if confidence == "medium" else 0.15
    return overrides


def run_portfolio_scenario_lab(
    db: Session,
    user_id: int,
    payload: PortfolioScenarioLabIn,
    *,
    target_type: str = "bought",
) -> PortfolioScenarioLabOut:
    resolved = resolve_portfolio_macro_scenario(payload.text)
    evaluator = (
        evaluate_custom_watch_target_stress_scenario
        if str(target_type).strip().lower() == "watch"
        else evaluate_custom_bought_target_stress_scenario
    )
    factor_overrides = _factor_overrides_from_resolved(resolved)
    scenario = evaluator(
        db,
        user_id,
        code="scenario_lab_preview",
        name=resolved.name,
        description=resolved.description,
        rules=resolved.rules,
        factor_overrides=factor_overrides,
        propagation_lambda=float(factor_overrides.get("propagation_lambda") or 0.22),
        position_limit=int(payload.position_limit),
    )
    return PortfolioScenarioLabOut(
        parse={
            "input_text": payload.text,
            "matched_template_code": resolved.matched_template_code,
            "matched_template_name": resolved.matched_template_name,
            "matched_template_codes": resolved.matched_template_codes,
            "matched_template_names": resolved.matched_template_names,
            "confidence": resolved.confidence,
            "extracted_shock_pct": resolved.extracted_shock_pct,
            "headline": resolved.headline,
            "explanation": resolved.explanation,
            "clauses": [
                {
                    "text": clause.text,
                    "parser": clause.parser,
                    "confidence": clause.confidence,
                    "headline": clause.headline,
                    "explanation": clause.explanation,
                    "matched_template_code": clause.matched_template_code,
                    "matched_template_name": clause.matched_template_name,
                    "extracted_shock_pct": clause.extracted_shock_pct,
                    "extracted_bp": clause.extracted_bp,
                    "rules": [custom_rule_label(rule) for rule in clause.rules],
                }
                for clause in resolved.clauses
            ],
        },
        scenario=scenario,
        beneficiaries=resolved.beneficiaries,
        losers=resolved.losers,
    )
