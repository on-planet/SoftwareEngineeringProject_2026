from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user_bought_target import UserBoughtTarget
from app.models.user_watch_target import UserWatchTarget
from app.schemas.user_targets import BoughtTargetUpsertIn


def normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def list_watch_targets(db: Session, user_id: int) -> list[UserWatchTarget]:
    return (
        db.query(UserWatchTarget)
        .filter(UserWatchTarget.user_id == user_id)
        .order_by(UserWatchTarget.updated_at.desc(), UserWatchTarget.symbol.asc())
        .all()
    )


def upsert_watch_target(db: Session, user_id: int, symbol: str) -> UserWatchTarget | None:
    normalized = normalize_symbol(symbol)
    if not normalized:
        return None
    item = (
        db.query(UserWatchTarget)
        .filter(UserWatchTarget.user_id == user_id, UserWatchTarget.symbol == normalized)
        .first()
    )
    if item is None:
        item = UserWatchTarget(user_id=user_id, symbol=normalized)
        db.add(item)
    db.commit()
    db.refresh(item)
    return item


def batch_upsert_watch_targets(db: Session, user_id: int, symbols: list[str]) -> list[UserWatchTarget]:
    normalized_symbols = []
    seen = set()
    for raw in symbols:
        normalized = normalize_symbol(raw)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        normalized_symbols.append(normalized)
    if not normalized_symbols:
        return list_watch_targets(db, user_id)
    for symbol in normalized_symbols:
        current = (
            db.query(UserWatchTarget)
            .filter(UserWatchTarget.user_id == user_id, UserWatchTarget.symbol == symbol)
            .first()
        )
        if current is None:
            db.add(UserWatchTarget(user_id=user_id, symbol=symbol))
    db.commit()
    return list_watch_targets(db, user_id)


def delete_watch_target(db: Session, user_id: int, symbol: str) -> bool:
    normalized = normalize_symbol(symbol)
    if not normalized:
        return False
    item = (
        db.query(UserWatchTarget)
        .filter(UserWatchTarget.user_id == user_id, UserWatchTarget.symbol == normalized)
        .first()
    )
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True


def list_bought_targets(db: Session, user_id: int) -> list[UserBoughtTarget]:
    return (
        db.query(UserBoughtTarget)
        .filter(UserBoughtTarget.user_id == user_id)
        .order_by(UserBoughtTarget.updated_at.desc(), UserBoughtTarget.symbol.asc())
        .all()
    )


def upsert_bought_target(db: Session, user_id: int, payload: BoughtTargetUpsertIn) -> UserBoughtTarget | None:
    normalized = normalize_symbol(payload.symbol)
    if not normalized:
        return None
    item = (
        db.query(UserBoughtTarget)
        .filter(UserBoughtTarget.user_id == user_id, UserBoughtTarget.symbol == normalized)
        .first()
    )
    if item is None:
        item = UserBoughtTarget(
            user_id=user_id,
            symbol=normalized,
            buy_price=float(payload.buy_price),
            lots=float(payload.lots),
            buy_date=payload.buy_date,
            fee=float(payload.fee),
            note=str(payload.note or ""),
        )
        db.add(item)
    else:
        item.buy_price = float(payload.buy_price)
        item.lots = float(payload.lots)
        item.buy_date = payload.buy_date
        item.fee = float(payload.fee)
        item.note = str(payload.note or "")
    db.commit()
    db.refresh(item)
    return item


def batch_upsert_bought_targets(
    db: Session,
    user_id: int,
    payloads: list[BoughtTargetUpsertIn],
) -> list[UserBoughtTarget]:
    if not payloads:
        return list_bought_targets(db, user_id)
    latest_by_symbol: dict[str, BoughtTargetUpsertIn] = {}
    for payload in payloads:
        normalized = normalize_symbol(payload.symbol)
        if not normalized:
            continue
        latest_by_symbol[normalized] = payload
    for symbol, payload in latest_by_symbol.items():
        current = (
            db.query(UserBoughtTarget)
            .filter(UserBoughtTarget.user_id == user_id, UserBoughtTarget.symbol == symbol)
            .first()
        )
        if current is None:
            current = UserBoughtTarget(user_id=user_id, symbol=symbol)
            db.add(current)
        current.buy_price = float(payload.buy_price)
        current.lots = float(payload.lots)
        current.buy_date = payload.buy_date
        current.fee = float(payload.fee)
        current.note = str(payload.note or "")
    db.commit()
    return list_bought_targets(db, user_id)


def delete_bought_target(db: Session, user_id: int, symbol: str) -> bool:
    normalized = normalize_symbol(symbol)
    if not normalized:
        return False
    item = (
        db.query(UserBoughtTarget)
        .filter(UserBoughtTarget.user_id == user_id, UserBoughtTarget.symbol == normalized)
        .first()
    )
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
