from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.buyback import Buyback
from app.schemas.buyback import BuybackCreate, BuybackUpdate
from app.utils.query_params import SortOrder


def list_buyback(
    db: Session,
    symbol: str,
    limit: int = 50,
    offset: int = 0,
    start: date | None = None,
    end: date | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    sort: SortOrder = "desc",
):
    """List buyback disclosures by symbol."""
    query = db.query(Buyback).filter(Buyback.symbol == symbol)
    if start is not None:
        query = query.filter(Buyback.date >= start)
    if end is not None:
        query = query.filter(Buyback.date <= end)
    if min_amount is not None:
        query = query.filter(Buyback.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(Buyback.amount <= max_amount)
    total = query.count()
    ordering = Buyback.date.asc() if sort == "asc" else Buyback.date.desc()
    items = (
        query.order_by(ordering)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return items, total


def create_buyback(db: Session, payload: BuybackCreate):
    item = Buyback(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_buyback(db: Session, symbol: str, buyback_date, payload: BuybackUpdate):
    item = (
        db.query(Buyback)
        .filter(Buyback.symbol == symbol, Buyback.date == buyback_date)
        .first()
    )
    if item is None:
        return None
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_buyback(db: Session, symbol: str, buyback_date) -> bool:
    item = (
        db.query(Buyback)
        .filter(Buyback.symbol == symbol, Buyback.date == buyback_date)
        .first()
    )
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
