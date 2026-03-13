from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.insider_trade import InsiderTrade
from app.schemas.insider_trade import InsiderTradeCreate, InsiderTradeUpdate
from app.utils.query_params import SortOrder


def list_insider_trades(
    db: Session,
    symbol: str,
    limit: int = 50,
    offset: int = 0,
    start: date | None = None,
    end: date | None = None,
    trade_types: list[str] | None = None,
    min_shares: float | None = None,
    max_shares: float | None = None,
    sort: SortOrder = "desc",
):
    """List insider trades by symbol."""
    query = db.query(InsiderTrade).filter(InsiderTrade.symbol == symbol)
    if trade_types:
        query = query.filter(InsiderTrade.type.in_(trade_types))
    if start is not None:
        query = query.filter(InsiderTrade.date >= start)
    if end is not None:
        query = query.filter(InsiderTrade.date <= end)
    if min_shares is not None:
        query = query.filter(InsiderTrade.shares >= min_shares)
    if max_shares is not None:
        query = query.filter(InsiderTrade.shares <= max_shares)
    total = query.count()
    ordering = InsiderTrade.date.asc() if sort == "asc" else InsiderTrade.date.desc()
    items = (
        query.order_by(ordering)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return items, total


def create_insider_trade(db: Session, payload: InsiderTradeCreate):
    item = InsiderTrade(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_insider_trade(db: Session, trade_id: int, payload: InsiderTradeUpdate):
    item = db.query(InsiderTrade).filter(InsiderTrade.id == trade_id).first()
    if item is None:
        return None
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_insider_trade(db: Session, trade_id: int) -> bool:
    item = db.query(InsiderTrade).filter(InsiderTrade.id == trade_id).first()
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
