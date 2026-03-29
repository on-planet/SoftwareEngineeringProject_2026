from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.schemas.portfolio_diagnostics import PortfolioDiagnosticsOut
from app.services.cache_utils import build_cache_key
from app.services.portfolio_macro_scenarios import build_macro_scenario_from_code
from app.services.portfolio_snapshot_service import (
    HoldingSnapshot,
    load_bought_target_snapshots,
    load_watch_target_snapshots,
    sector_has_keyword,
)
from app.services.portfolio_stress_service import (
    ScenarioDefinition,
    build_custom_shock_function,
    custom_rule_label,
    evaluate_scenario,
)

PORTFOLIO_DIAGNOSTICS_CACHE_TTL = 120
PORTFOLIO_DIAGNOSTICS_VERSION = "v1"


def _sum_weights(snapshots: list[HoldingSnapshot], matcher) -> float:
    return sum(snapshot.weight for snapshot in snapshots if matcher(snapshot))


def _score_level(value: float) -> str:
    if value >= 0.45:
        return "high"
    if value >= 0.22:
        return "medium"
    return "low"


def _style_exposures(snapshots: list[HoldingSnapshot]) -> list[dict[str, object]]:
    finance = _sum_weights(
        snapshots,
        lambda item: item.sector == "金融"
        or sector_has_keyword(item, ("bank", "broker", "insurance", "finance", "fintech")),
    )
    growth = _sum_weights(
        snapshots,
        lambda item: item.sector in {"科技", "电信传媒"}
        or sector_has_keyword(item, ("tech", "internet", "software", "semiconductor", "media", "telecom", "ai", "cloud")),
    )
    defensive = _sum_weights(
        snapshots,
        lambda item: item.sector in {"公用事业", "医疗健康", "消费"}
        or sector_has_keyword(item, ("utility", "health", "medical", "pharma", "consumer", "staple")),
    )
    cyclical = _sum_weights(
        snapshots,
        lambda item: item.sector in {"房地产", "原材料", "工业制造", "交通运输", "航空旅游", "能源"}
        or sector_has_keyword(item, ("property", "material", "steel", "metal", "industrial", "transport", "shipping", "airline", "energy", "oil", "coal")),
    )
    property_chain = _sum_weights(
        snapshots,
        lambda item: item.sector == "房地产"
        or sector_has_keyword(item, ("property", "real estate", "building", "construction", "cement", "furniture")),
    )
    export_chain = _sum_weights(
        snapshots,
        lambda item: item.market in {"HK", "US"}
        or item.sector in {"科技", "工业制造", "家居家电"}
        or sector_has_keyword(item, ("export", "appliance", "electronics", "manufacturing", "hardware", "textile")),
    )
    styles = [
        {
            "code": "finance",
            "label": "金融暴露",
            "score": finance,
            "explanation": f"金融、银行、券商和保险相关持仓约占 {_score_level(finance)} 区间。",
        },
        {
            "code": "growth",
            "label": "成长暴露",
            "score": growth,
            "explanation": f"科技、互联网和传媒链持仓约占 {_score_level(growth)} 区间。",
        },
        {
            "code": "defensive",
            "label": "防御暴露",
            "score": defensive,
            "explanation": f"消费、公用事业和医疗等防御资产约占 {_score_level(defensive)} 区间。",
        },
        {
            "code": "cyclical",
            "label": "周期暴露",
            "score": cyclical,
            "explanation": f"地产、资源、制造和运输等顺周期资产约占 {_score_level(cyclical)} 区间。",
        },
        {
            "code": "property_chain",
            "label": "地产链暴露",
            "score": property_chain,
            "explanation": "地产、建材、家居和相关后周期链条的合计权重。",
        },
        {
            "code": "export_chain",
            "label": "出口链暴露",
            "score": export_chain,
            "explanation": "港股/美股以及出口制造相关持仓的近似权重。",
        },
    ]
    styles.sort(key=lambda item: float(item["score"]), reverse=True)
    return styles


def _macro_sensitivities(
    snapshots: list[HoldingSnapshot],
    *,
    total_value: float,
) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    for code, label in (
        ("rate_up", "利率上行敏感度"),
        ("rmb_depreciation", "人民币贬值敏感度"),
        ("oil_up", "油价上行敏感度"),
        ("property_easing", "地产宽松敏感度"),
    ):
        resolved = build_macro_scenario_from_code(code)
        scenario = ScenarioDefinition(
            code=code,
            name=resolved.name,
            description=resolved.description,
            rules=tuple(custom_rule_label(rule) for rule in resolved.rules),
            shock_fn=build_custom_shock_function(resolved.rules),
        )
        evaluated = evaluate_scenario(
            scenario,
            snapshots,
            total_value=total_value,
            position_limit=6,
        )
        change_pct = float(evaluated.get("portfolio_change_pct") or 0.0)
        items.append(
            {
                "code": code,
                "label": label,
                "scenario_name": resolved.name,
                "portfolio_change_pct": change_pct,
                "direction": "benefit" if change_pct > 0.002 else "hurt" if change_pct < -0.002 else "neutral",
                "explanation": resolved.description,
            }
        )
    items.sort(key=lambda item: abs(float(item["portfolio_change_pct"])), reverse=True)
    return items


def _portrait_tags(
    styles: list[dict[str, object]],
    macro_sensitivities: list[dict[str, object]],
    *,
    top3_weight: float,
    sector_count: int,
) -> list[dict[str, str]]:
    style_map = {str(item["code"]): item for item in styles}
    tags: list[dict[str, str]] = []

    finance_score = float(style_map.get("finance", {}).get("score", 0.0))
    growth_score = float(style_map.get("growth", {}).get("score", 0.0))
    cyclical_score = float(style_map.get("cyclical", {}).get("score", 0.0))
    property_score = float(style_map.get("property_chain", {}).get("score", 0.0))

    if finance_score >= 0.35:
        tags.append(
            {
                "code": "high_finance",
                "label": "高金融暴露",
                "tone": "risk",
                "explanation": "金融链权重偏高，组合波动会更容易受信用和利率预期影响。",
            }
        )
    if growth_score <= 0.18:
        tags.append(
            {
                "code": "low_growth",
                "label": "低成长暴露",
                "tone": "info",
                "explanation": "成长和高弹性资产占比较低，风格更偏价值或防御。",
            }
        )
    elif growth_score >= 0.35:
        tags.append(
            {
                "code": "high_growth",
                "label": "高成长暴露",
                "tone": "risk",
                "explanation": "科技和成长风格占比较高，估值和利率波动弹性更大。",
            }
        )
    if cyclical_score >= 0.45 or property_score >= 0.25:
        tags.append(
            {
                "code": "cyclical_tilt",
                "label": "偏顺周期",
                "tone": "info",
                "explanation": "地产、资源、制造或运输等顺周期资产占比较高。",
            }
        )
    if top3_weight >= 0.62:
        tags.append(
            {
                "code": "concentrated",
                "label": "持仓集中度偏高",
                "tone": "risk",
                "explanation": "前三大持仓权重偏高，组合更容易受个别标的驱动。",
            }
        )
    elif top3_weight <= 0.42 and sector_count >= 4:
        tags.append(
            {
                "code": "diversified",
                "label": "分散度较好",
                "tone": "positive",
                "explanation": "前三大持仓占比不高且行业分布较分散。",
            }
        )

    top_macro = macro_sensitivities[0] if macro_sensitivities else None
    if top_macro and abs(float(top_macro["portfolio_change_pct"])) >= 0.02:
        macro_code = str(top_macro["code"])
        if macro_code == "rate_up":
            tags.append(
                {
                    "code": "rate_sensitive",
                    "label": "对宏观利率敏感",
                    "tone": "risk" if float(top_macro["portfolio_change_pct"]) < 0 else "positive",
                    "explanation": "当前组合在利率上行场景下有明显弹性。",
                }
            )
        elif macro_code == "property_easing" and float(top_macro["portfolio_change_pct"]) > 0:
            tags.append(
                {
                    "code": "property_policy_benefit",
                    "label": "受益于地产宽松",
                    "tone": "positive",
                    "explanation": "地产与相关顺周期链条在组合中的权重较高。",
                }
            )
        elif macro_code == "rmb_depreciation":
            tags.append(
                {
                    "code": "fx_sensitive",
                    "label": "对人民币汇率敏感",
                    "tone": "positive" if float(top_macro["portfolio_change_pct"]) > 0 else "risk",
                    "explanation": "出口链或外币成本敏感资产在组合中占有一定比重。",
                }
            )

    deduped: list[dict[str, str]] = []
    seen = set()
    for tag in tags:
        code = str(tag["code"])
        if code in seen:
            continue
        seen.add(code)
        deduped.append(tag)
        if len(deduped) >= 5:
            break
    return deduped


def _build_overview(
    portrait: list[dict[str, str]],
    sector_exposure: list[dict[str, object]],
    macro_sensitivities: list[dict[str, object]],
    *,
    top3_weight: float,
    scope_label: str,
) -> str:
    lead = "、".join(tag["label"] for tag in portrait[:3]) or "均衡配置"
    top_sector = str(sector_exposure[0]["label"]) if sector_exposure else "未分类"
    top_macro = macro_sensitivities[0] if macro_sensitivities else None
    macro_text = "宏观情景弹性有限"
    if top_macro and abs(float(top_macro["portfolio_change_pct"])) >= 0.01:
        macro_text = (
            f"在{top_macro['scenario_name']}场景下组合约变动 {float(top_macro['portfolio_change_pct']) * 100:+.1f}%"
        )
    return f"{scope_label}当前以 {top_sector} 为主要暴露，前三大持仓占比约 {top3_weight * 100:.0f}%，整体画像偏向 {lead}；{macro_text}。"

def _build_portfolio_diagnostics(
    *,
    snapshots: list[HoldingSnapshot],
    total_value: float,
    total_cost: float,
    as_of,
    empty_overview: str,
    scope_label: str,
) -> PortfolioDiagnosticsOut:
    if not snapshots:
        return PortfolioDiagnosticsOut(
            summary={
                "as_of": as_of,
                "holdings_count": 0,
                "total_cost": 0.0,
                "total_value": 0.0,
                "total_pnl": 0.0,
                "total_pnl_pct": 0.0,
                "sector_count": 0,
                "top_sector": None,
                "top_market": None,
                "top3_weight": 0.0,
            },
            overview=empty_overview,
        )

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost) if total_cost else 0.0

    sector_bucket: dict[str, float] = defaultdict(float)
    market_bucket: dict[str, float] = defaultdict(float)
    for snapshot in snapshots:
        sector_bucket[snapshot.sector or "未分类"] += snapshot.current_value
        market_bucket[snapshot.market or "UNKNOWN"] += snapshot.current_value

    sector_exposure = [
        {
            "label": label,
            "value": value,
            "weight": (value / total_value) if total_value else 0.0,
        }
        for label, value in sector_bucket.items()
    ]
    sector_exposure.sort(key=lambda item: float(item["weight"]), reverse=True)

    market_exposure = [
        {
            "label": label,
            "value": value,
            "weight": (value / total_value) if total_value else 0.0,
        }
        for label, value in market_bucket.items()
    ]
    market_exposure.sort(key=lambda item: float(item["weight"]), reverse=True)

    top_positions = [
        {
            "symbol": snapshot.symbol,
            "name": snapshot.name,
            "market": snapshot.market,
            "sector": snapshot.sector,
            "weight": snapshot.weight,
            "current_value": snapshot.current_value,
            "pnl_value": snapshot.pnl_value,
            "pnl_pct": snapshot.pnl_pct,
        }
        for snapshot in sorted(snapshots, key=lambda item: item.weight, reverse=True)[:6]
    ]
    top3_weight = sum(float(item["weight"]) for item in top_positions[:3])

    styles = _style_exposures(snapshots)
    macro_sensitivities = _macro_sensitivities(snapshots, total_value=total_value)
    portrait = _portrait_tags(
        styles,
        macro_sensitivities,
        top3_weight=top3_weight,
        sector_count=len(sector_exposure),
    )
    overview = _build_overview(
        portrait,
        sector_exposure,
        macro_sensitivities,
        top3_weight=top3_weight,
        scope_label=scope_label,
    )

    return PortfolioDiagnosticsOut(
        summary={
            "as_of": as_of,
            "holdings_count": len(snapshots),
            "total_cost": total_cost,
            "total_value": total_value,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl_pct,
            "sector_count": len(sector_exposure),
            "top_sector": str(sector_exposure[0]["label"]) if sector_exposure else None,
            "top_market": str(market_exposure[0]["label"]) if market_exposure else None,
            "top3_weight": top3_weight,
        },
        overview=overview,
        portrait=portrait,
        style_exposures=styles,
        macro_sensitivities=macro_sensitivities,
        sector_exposure=sector_exposure,
        market_exposure=market_exposure,
        top_positions=top_positions,
    )


def _get_portfolio_diagnostics(
    db: Session,
    user_id: int,
    *,
    cache_scope: str,
    snapshot_loader,
    empty_overview: str,
    scope_label: str,
) -> PortfolioDiagnosticsOut:
    cache_key = build_cache_key(
        cache_scope,
        user_id=user_id,
        version=PORTFOLIO_DIAGNOSTICS_VERSION,
    )
    cached = get_json(cache_key)
    if isinstance(cached, dict):
        try:
            return PortfolioDiagnosticsOut(**cached)
        except Exception:
            pass

    snapshots, total_value, total_cost, as_of = snapshot_loader(db, user_id)
    payload = _build_portfolio_diagnostics(
        snapshots=snapshots,
        total_value=total_value,
        total_cost=total_cost,
        as_of=as_of,
        empty_overview=empty_overview,
        scope_label=scope_label,
    )
    set_json(cache_key, payload.model_dump(mode="json"), ttl=PORTFOLIO_DIAGNOSTICS_CACHE_TTL)
    return payload


def get_bought_target_diagnostics(db: Session, user_id: int) -> PortfolioDiagnosticsOut:
    return _get_portfolio_diagnostics(
        db,
        user_id,
        cache_scope="user:bought-targets:diagnostics",
        snapshot_loader=load_bought_target_snapshots,
        empty_overview="暂无已买持仓，录入持仓后才会生成组合画像和宏观敏感度。",
        scope_label="组合",
    )


def get_watch_target_diagnostics(db: Session, user_id: int) -> PortfolioDiagnosticsOut:
    return _get_portfolio_diagnostics(
        db,
        user_id,
        cache_scope="user:watch-targets:diagnostics",
        snapshot_loader=load_watch_target_snapshots,
        empty_overview="暂无观察标的，添加后系统会按等权观察篮子生成画像和宏观敏感度。",
        scope_label="观察篮子",
    )
