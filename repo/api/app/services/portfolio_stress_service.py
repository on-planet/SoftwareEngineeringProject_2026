from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Callable

from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.schemas.portfolio_stress import PortfolioStressOut, PortfolioStressPreviewIn, PortfolioStressRuleIn
from app.services.cache_utils import build_cache_key
from app.services.portfolio_snapshot_service import (
    HoldingSnapshot,
    canonical_sector_label,
    load_bought_target_snapshots,
    load_watch_target_snapshots,
    sector_has_keyword,
)

PORTFOLIO_STRESS_CACHE_TTL = 120
DEFAULT_POSITION_LIMIT = 8
PORTFOLIO_STRESS_CACHE_VERSION = "v2"


@dataclass(frozen=True)
class ScenarioDefinition:
    code: str
    name: str
    description: str
    rules: tuple[str, ...]
    shock_fn: Callable[[HoldingSnapshot], float]


def _bank_sector_shock(snapshot: HoldingSnapshot) -> float:
    if snapshot.sector == "金融" or sector_has_keyword(snapshot, ("bank", "broker", "insurance", "finance", "fintech")):
        return -0.05
    return 0.0


def _hk_tech_shock(snapshot: HoldingSnapshot) -> float:
    if snapshot.market != "HK":
        return 0.0
    if snapshot.sector in {"科技", "电信传媒"}:
        return -0.08
    if sector_has_keyword(
        snapshot,
        (
            "tech",
            "technology",
            "internet",
            "software",
            "semiconductor",
            "media",
            "telecom",
            "ai",
            "cloud",
            "platform",
            "e-commerce",
            "ecommerce",
        ),
    ):
        return -0.08
    return 0.0


def _us_yield_up_shock(snapshot: HoldingSnapshot) -> float:
    if snapshot.sector == "金融":
        return 0.01
    if snapshot.sector in {"科技", "电信传媒"} or sector_has_keyword(
        snapshot,
        ("tech", "technology", "internet", "software", "semiconductor", "ai", "cloud", "growth"),
    ):
        return -0.06 if snapshot.market in {"HK", "US"} else -0.04
    if snapshot.sector == "房地产":
        return -0.05
    if snapshot.sector in {"公用事业", "医疗健康"}:
        return -0.03
    if snapshot.sector == "消费":
        return -0.02
    if snapshot.market in {"HK", "US"}:
        return -0.02
    return -0.01


SCENARIOS: tuple[ScenarioDefinition, ...] = (
    ScenarioDefinition(
        code="bank_sector_drop",
        name="银行板块回撤",
        description="假设银行和金融板块统一下跌 5%，观察组合对单一行业回撤的敏感度。",
        rules=("金融/银行持仓 -5%", "其他持仓 0%"),
        shock_fn=_bank_sector_shock,
    ),
    ScenarioDefinition(
        code="hk_tech_pullback",
        name="港股科技回撤",
        description="假设港股科技和互联网平台整体回撤 8%，评估组合对成长风格波动的弹性。",
        rules=("港股科技/互联网持仓 -8%", "其他持仓 0%"),
        shock_fn=_hk_tech_shock,
    ),
    ScenarioDefinition(
        code="us_yield_up_50bp",
        name="美债收益率上行",
        description="假设美债收益率上行 50bp，成长和利率敏感资产承压，金融板块小幅受益。",
        rules=("科技/传媒 -4%~-6%", "房地产 -5%", "公用事业/医疗 -3%", "金融 +1%", "其他 -1%~-2%"),
        shock_fn=_us_yield_up_shock,
    ),
)


def _serialize_bucket_rows(
    bucket_changes: dict[str, float],
    bucket_values: dict[str, float],
    total_value: float,
) -> list[dict[str, float | str]]:
    rows: list[dict[str, float | str]] = []
    for label, value_change in bucket_changes.items():
        affected_value = float(bucket_values.get(label) or 0.0)
        rows.append(
            {
                "label": label,
                "affected_value": affected_value,
                "portfolio_weight": (affected_value / total_value) if total_value else 0.0,
                "value_change": float(value_change),
            }
        )
    rows.sort(key=lambda item: abs(float(item["value_change"])), reverse=True)
    return rows


def clip_shock_pct(value: float) -> float:
    return max(-0.95, min(0.95, float(value)))


def scope_value_matches(rule: PortfolioStressRuleIn, snapshot: HoldingSnapshot) -> bool:
    scope_type = str(rule.scope_type or "").lower()
    scope_value = str(rule.scope_value or "").strip()
    if scope_type == "all":
        return True
    if not scope_value:
        return False
    if scope_type == "market":
        return snapshot.market.upper() == scope_value.upper()
    if scope_type == "symbol":
        return snapshot.symbol.upper() == scope_value.upper()
    if scope_type == "sector":
        target = canonical_sector_label(scope_value, snapshot.market).lower()
        return (
            target in snapshot.sector.lower()
            or target in snapshot.raw_sector.lower()
            or scope_value.lower() in snapshot.sector.lower()
            or scope_value.lower() in snapshot.raw_sector.lower()
        )
    return False


def custom_rule_label(rule: PortfolioStressRuleIn) -> str:
    shock_text = f"{rule.shock_pct * 100:+.1f}%"
    if rule.scope_type == "all":
        return f"全组合 {shock_text}"
    scope_name = {
        "market": "市场",
        "sector": "行业",
        "symbol": "股票",
    }.get(rule.scope_type, rule.scope_type)
    return f"{scope_name}:{rule.scope_value} {shock_text}"


def build_custom_shock_function(rules: list[PortfolioStressRuleIn]) -> Callable[[HoldingSnapshot], float]:
    normalized_rules = list(rules)

    def _shock(snapshot: HoldingSnapshot) -> float:
        total_shock = 0.0
        for rule in normalized_rules:
            if scope_value_matches(rule, snapshot):
                total_shock += float(rule.shock_pct)
        return clip_shock_pct(total_shock)

    return _shock


def evaluate_scenario(
    scenario: ScenarioDefinition,
    snapshots: list[HoldingSnapshot],
    *,
    total_value: float,
    position_limit: int,
) -> dict[str, object]:
    impacted_value = 0.0
    weighted_shock = 0.0
    portfolio_change = 0.0
    affected_positions: list[dict[str, object]] = []
    sector_changes: dict[str, float] = defaultdict(float)
    sector_values: dict[str, float] = defaultdict(float)
    market_changes: dict[str, float] = defaultdict(float)
    market_values: dict[str, float] = defaultdict(float)

    for snapshot in snapshots:
        shock_pct = float(scenario.shock_fn(snapshot))
        projected_value = snapshot.current_value * (1.0 + shock_pct)
        value_change = projected_value - snapshot.current_value
        portfolio_change += value_change
        if abs(shock_pct) < 1e-9:
            continue

        impacted_value += snapshot.current_value
        weighted_shock += snapshot.current_value * shock_pct
        sector_key = snapshot.sector or "未分类"
        market_key = snapshot.market or "UNKNOWN"
        sector_changes[sector_key] += value_change
        sector_values[sector_key] += snapshot.current_value
        market_changes[market_key] += value_change
        market_values[market_key] += snapshot.current_value
        affected_positions.append(
            {
                "symbol": snapshot.symbol,
                "name": snapshot.name,
                "market": snapshot.market,
                "sector": snapshot.sector,
                "current_price": snapshot.current_price,
                "current_value": snapshot.current_value,
                "weight": snapshot.weight,
                "shock_pct": shock_pct,
                "projected_value": projected_value,
                "value_change": value_change,
            }
        )

    affected_positions.sort(key=lambda item: abs(float(item["value_change"])), reverse=True)
    projected_value = total_value + portfolio_change
    average_shock_pct = (weighted_shock / impacted_value) if impacted_value else None
    return {
        "code": scenario.code,
        "name": scenario.name,
        "description": scenario.description,
        "rules": list(scenario.rules),
        "projected_value": projected_value,
        "portfolio_change": portfolio_change,
        "portfolio_change_pct": (portfolio_change / total_value) if total_value else 0.0,
        "loss_amount": max(-portfolio_change, 0.0),
        "loss_pct": (max(-portfolio_change, 0.0) / total_value) if total_value else 0.0,
        "impacted_value": impacted_value,
        "impacted_weight": (impacted_value / total_value) if total_value else 0.0,
        "average_shock_pct": average_shock_pct,
        "affected_positions": affected_positions[: max(1, position_limit)],
        "sector_impacts": _serialize_bucket_rows(sector_changes, sector_values, total_value),
        "market_impacts": _serialize_bucket_rows(market_changes, market_values, total_value),
    }


def _evaluate_custom_stress_scenario(
    snapshots: list[HoldingSnapshot],
    *,
    total_value: float,
    code: str,
    name: str,
    description: str,
    rules: list[PortfolioStressRuleIn],
    position_limit: int = DEFAULT_POSITION_LIMIT,
) -> dict[str, object]:
    scenario = ScenarioDefinition(
        code=code,
        name=str(name).strip(),
        description=str(description or "").strip(),
        rules=tuple(custom_rule_label(rule) for rule in rules),
        shock_fn=build_custom_shock_function(rules),
    )
    return evaluate_scenario(
        scenario,
        snapshots,
        total_value=total_value,
        position_limit=max(1, int(position_limit)),
    )


def evaluate_custom_bought_target_stress_scenario(
    db: Session,
    user_id: int,
    *,
    code: str,
    name: str,
    description: str,
    rules: list[PortfolioStressRuleIn],
    position_limit: int = DEFAULT_POSITION_LIMIT,
) -> dict[str, object]:
    snapshots, total_value, _, _ = load_bought_target_snapshots(db, user_id)
    return _evaluate_custom_stress_scenario(
        snapshots,
        total_value=total_value,
        code=code,
        name=name,
        description=description,
        rules=rules,
        position_limit=position_limit,
    )


def evaluate_custom_watch_target_stress_scenario(
    db: Session,
    user_id: int,
    *,
    code: str,
    name: str,
    description: str,
    rules: list[PortfolioStressRuleIn],
    position_limit: int = DEFAULT_POSITION_LIMIT,
) -> dict[str, object]:
    snapshots, total_value, _, _ = load_watch_target_snapshots(db, user_id)
    return _evaluate_custom_stress_scenario(
        snapshots,
        total_value=total_value,
        code=code,
        name=name,
        description=description,
        rules=rules,
        position_limit=position_limit,
    )


def _build_portfolio_stress_payload(
    snapshots: list[HoldingSnapshot],
    *,
    total_value: float,
    as_of,
    position_limit: int,
) -> PortfolioStressOut:
    scenarios = [
        evaluate_scenario(
            scenario,
            snapshots,
            total_value=total_value,
            position_limit=position_limit,
        )
        for scenario in SCENARIOS
    ]
    worst = max(scenarios, key=lambda item: float(item.get("loss_amount") or 0.0), default=None)
    return PortfolioStressOut(
        summary={
            "as_of": as_of,
            "holdings_count": len(snapshots),
            "total_value": total_value,
            "scenario_count": len(scenarios),
            "worst_scenario_code": str(worst.get("code")) if worst else None,
            "worst_scenario_name": str(worst.get("name")) if worst else None,
            "worst_loss_amount": float(worst.get("loss_amount") or 0.0) if worst else 0.0,
            "worst_loss_pct": float(worst.get("loss_pct") or 0.0) if worst else 0.0,
            "max_impacted_weight": max((float(item.get("impacted_weight") or 0.0) for item in scenarios), default=0.0),
        },
        scenarios=scenarios,
    )


def _get_portfolio_stress_test(
    db: Session,
    user_id: int,
    *,
    cache_scope: str,
    snapshot_loader,
    position_limit: int = DEFAULT_POSITION_LIMIT,
) -> PortfolioStressOut:
    cache_key = build_cache_key(
        cache_scope,
        user_id=user_id,
        position_limit=position_limit,
        version=PORTFOLIO_STRESS_CACHE_VERSION,
    )
    cached = get_json(cache_key)
    if isinstance(cached, dict):
        try:
            return PortfolioStressOut(**cached)
        except Exception:
            pass

    snapshots, total_value, _, as_of = snapshot_loader(db, user_id)
    payload = _build_portfolio_stress_payload(
        snapshots,
        total_value=total_value,
        as_of=as_of,
        position_limit=position_limit,
    )
    set_json(cache_key, payload.model_dump(mode="json"), ttl=PORTFOLIO_STRESS_CACHE_TTL)
    return payload


def get_bought_target_stress_test(
    db: Session,
    user_id: int,
    *,
    position_limit: int = DEFAULT_POSITION_LIMIT,
) -> PortfolioStressOut:
    return _get_portfolio_stress_test(
        db,
        user_id,
        cache_scope="user:bought-targets:stress-test",
        snapshot_loader=load_bought_target_snapshots,
        position_limit=position_limit,
    )


def get_watch_target_stress_test(
    db: Session,
    user_id: int,
    *,
    position_limit: int = DEFAULT_POSITION_LIMIT,
) -> PortfolioStressOut:
    return _get_portfolio_stress_test(
        db,
        user_id,
        cache_scope="user:watch-targets:stress-test",
        snapshot_loader=load_watch_target_snapshots,
        position_limit=position_limit,
    )


def preview_custom_bought_target_stress_test(
    db: Session,
    user_id: int,
    payload: PortfolioStressPreviewIn,
) -> dict[str, object]:
    return evaluate_custom_bought_target_stress_scenario(
        db,
        user_id,
        code="custom_preview",
        name=str(payload.name).strip(),
        description=str(payload.description or "").strip() or "用户自定义压力场景预览",
        rules=list(payload.rules),
        position_limit=int(payload.position_limit),
    )


def preview_custom_watch_target_stress_test(
    db: Session,
    user_id: int,
    payload: PortfolioStressPreviewIn,
) -> dict[str, object]:
    return evaluate_custom_watch_target_stress_scenario(
        db,
        user_id,
        code="custom_preview",
        name=str(payload.name).strip(),
        description=str(payload.description or "").strip() or "用户自定义压力场景预览",
        rules=list(payload.rules),
        position_limit=int(payload.position_limit),
    )
