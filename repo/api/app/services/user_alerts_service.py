from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy.orm import Session

from app.models.user_alert_rule import UserAlertRule
from app.schemas.user_alerts import (
    AlertCenterOut,
    AlertRuleCreateIn,
    AlertRuleEvaluationOut,
    AlertRuleOut,
    AlertRuleUpdateIn,
)
from app.services.event_timeline_service import list_event_timeline
from app.services.research_service import get_stock_research
from app.services.stock_service import get_stock_compare_batch


def normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def list_alert_rules(db: Session, user_id: int) -> list[UserAlertRule]:
    return (
        db.query(UserAlertRule)
        .filter(UserAlertRule.user_id == user_id)
        .order_by(UserAlertRule.updated_at.desc(), UserAlertRule.id.desc())
        .all()
    )


def create_alert_rule(db: Session, user_id: int, payload: AlertRuleCreateIn) -> UserAlertRule:
    item = UserAlertRule(
        user_id=user_id,
        name=str(payload.name).strip(),
        rule_type=str(payload.rule_type),
        symbol=normalize_symbol(payload.symbol),
        price_operator=payload.price_operator,
        threshold=payload.threshold,
        event_type=str(payload.event_type or "").strip() or None,
        research_kind=payload.research_kind,
        lookback_days=int(payload.lookback_days),
        is_active=bool(payload.is_active),
        note=str(payload.note or ""),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_alert_rule(
    db: Session,
    user_id: int,
    rule_id: int,
    payload: AlertRuleUpdateIn,
) -> UserAlertRule | None:
    item = (
        db.query(UserAlertRule)
        .filter(UserAlertRule.user_id == user_id, UserAlertRule.id == rule_id)
        .first()
    )
    if item is None:
        return None
    if payload.name is not None:
        item.name = str(payload.name).strip()
    if payload.price_operator is not None:
        item.price_operator = payload.price_operator
    if payload.threshold is not None:
        item.threshold = float(payload.threshold)
    if payload.event_type is not None:
        item.event_type = str(payload.event_type or "").strip() or None
    if payload.research_kind is not None:
        item.research_kind = payload.research_kind
    if payload.lookback_days is not None:
        item.lookback_days = int(payload.lookback_days)
    if payload.is_active is not None:
        item.is_active = bool(payload.is_active)
    if payload.note is not None:
        item.note = str(payload.note)
    db.commit()
    db.refresh(item)
    return item


def delete_alert_rule(db: Session, user_id: int, rule_id: int) -> bool:
    item = (
        db.query(UserAlertRule)
        .filter(UserAlertRule.user_id == user_id, UserAlertRule.id == rule_id)
        .first()
    )
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True


def _parse_datetime(value) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _build_base_rule_out(item: UserAlertRule) -> AlertRuleOut:
    return AlertRuleOut(
        id=int(item.id),
        name=str(item.name or ""),
        rule_type=str(item.rule_type),
        symbol=normalize_symbol(item.symbol),
        price_operator=item.price_operator,
        threshold=item.threshold,
        event_type=item.event_type,
        research_kind=item.research_kind,
        lookback_days=int(item.lookback_days or 7),
        is_active=bool(item.is_active),
        note=str(item.note or ""),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _evaluate_price_rule(item: UserAlertRule, price_payload: dict | None) -> AlertRuleEvaluationOut:
    rule = _build_base_rule_out(item)
    if not item.is_active:
        return AlertRuleEvaluationOut(
            **rule.model_dump(),
            triggered=False,
            status="inactive",
            status_message="规则已停用",
        )
    current = None
    if isinstance(price_payload, dict):
        quote = price_payload.get("quote")
        if isinstance(quote, dict):
            value = quote.get("current")
            if isinstance(value, (int, float)):
                current = float(value)
    if current is None:
        return AlertRuleEvaluationOut(
            **rule.model_dump(),
            triggered=False,
            status="unavailable",
            status_message="缺少最新价格，暂时无法评估",
        )
    threshold = float(item.threshold or 0)
    triggered = current >= threshold if item.price_operator == "gte" else current <= threshold
    operator_text = ">=" if item.price_operator == "gte" else "<="
    return AlertRuleEvaluationOut(
        **rule.model_dump(),
        triggered=triggered,
        status="triggered" if triggered else "watching",
        status_message=f"最新价 {current:.2f} {operator_text} {threshold:.2f}",
        latest_value=current,
        matched_at=datetime.now(UTC).isoformat() if triggered else None,
    )


def _evaluate_event_rule(db: Session, item: UserAlertRule) -> AlertRuleEvaluationOut:
    rule = _build_base_rule_out(item)
    if not item.is_active:
        return AlertRuleEvaluationOut(
            **rule.model_dump(),
            triggered=False,
            status="inactive",
            status_message="规则已停用",
        )
    end = date.today()
    start = end - timedelta(days=max(int(item.lookback_days or 1) - 1, 0))
    items, _ = list_event_timeline(
        db,
        symbols=[normalize_symbol(item.symbol)],
        event_types=[str(item.event_type)] if item.event_type else None,
        start=start,
        end=end,
        limit=1,
        offset=0,
        sort="desc",
    )
    latest = items[0] if items else None
    if latest is None:
        return AlertRuleEvaluationOut(
            **rule.model_dump(),
            triggered=False,
            status="watching",
            status_message=f"最近 {item.lookback_days} 天未发现目标事件",
        )
    return AlertRuleEvaluationOut(
        **rule.model_dump(),
        triggered=True,
        status="triggered",
        status_message=f"最近 {item.lookback_days} 天出现 {latest.type} 事件",
        matched_at=latest.date.isoformat(),
        context_title=latest.title,
    )


def _evaluate_earnings_rule(item: UserAlertRule) -> AlertRuleEvaluationOut:
    rule = _build_base_rule_out(item)
    if not item.is_active:
        return AlertRuleEvaluationOut(
            **rule.model_dump(),
            triggered=False,
            status="inactive",
            status_message="规则已停用",
        )
    payload = get_stock_research(normalize_symbol(item.symbol), report_limit=10, forecast_limit=10) or {}
    research_kind = str(item.research_kind or "all")
    candidates: list[tuple[str, dict, datetime]] = []
    kinds = ("report", "earning_forecast") if research_kind == "all" else (research_kind,)
    since = datetime.combine(date.today() - timedelta(days=max(int(item.lookback_days or 1) - 1, 0)), time.min)
    for kind in kinds:
        source_key = "reports" if kind == "report" else "earning_forecasts"
        for raw in payload.get(source_key) or []:
            if not isinstance(raw, dict):
                continue
            published_at = _parse_datetime(raw.get("published_at"))
            if published_at is None or published_at < since:
                continue
            candidates.append((kind, raw, published_at))
    candidates.sort(key=lambda item_tuple: item_tuple[2], reverse=True)
    if not candidates:
        label = "财报或盈利预测" if research_kind == "all" else ("财报" if research_kind == "report" else "盈利预测")
        return AlertRuleEvaluationOut(
            **rule.model_dump(),
            triggered=False,
            status="watching",
            status_message=f"最近 {item.lookback_days} 天未出现新的{label}",
        )
    latest_kind, latest_raw, latest_published_at = candidates[0]
    label = "财报" if latest_kind == "report" else "盈利预测"
    return AlertRuleEvaluationOut(
        **rule.model_dump(),
        triggered=True,
        status="triggered",
        status_message=f"最近 {item.lookback_days} 天出现新的{label}",
        matched_at=latest_published_at.isoformat(),
        context_title=str(latest_raw.get("title") or label),
    )


def get_alert_center(db: Session, user_id: int) -> AlertCenterOut:
    rules = list_alert_rules(db, user_id)
    price_symbols = [normalize_symbol(item.symbol) for item in rules if item.rule_type == "price" and item.is_active]
    price_payloads = {
        str(item.get("symbol") or ""): item
        for item in get_stock_compare_batch(db, price_symbols, prefer_live=False)
    }

    evaluations: list[AlertRuleEvaluationOut] = []
    for item in rules:
        if item.rule_type == "price":
            evaluations.append(_evaluate_price_rule(item, price_payloads.get(normalize_symbol(item.symbol))))
        elif item.rule_type == "event":
            evaluations.append(_evaluate_event_rule(db, item))
        else:
            evaluations.append(_evaluate_earnings_rule(item))

    triggered = sum(1 for item in evaluations if item.triggered)
    return AlertCenterOut(total=len(evaluations), triggered=triggered, items=evaluations)
