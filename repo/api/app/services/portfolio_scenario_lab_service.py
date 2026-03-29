from __future__ import annotations

from sqlalchemy.orm import Session

from app.schemas.portfolio_stress import PortfolioScenarioLabIn, PortfolioScenarioLabOut
from app.services.portfolio_macro_scenarios import resolve_portfolio_macro_scenario
from app.services.portfolio_stress_service import (
    custom_rule_label,
    evaluate_custom_bought_target_stress_scenario,
    evaluate_custom_watch_target_stress_scenario,
)


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
    scenario = evaluator(
        db,
        user_id,
        code="scenario_lab_preview",
        name=resolved.name,
        description=resolved.description,
        rules=resolved.rules,
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
