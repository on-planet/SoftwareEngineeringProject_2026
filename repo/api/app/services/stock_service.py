from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.cache import get_json
from app.models.stocks import Stock
from app.models.daily_prices import DailyPrice
from app.schemas.stock import StockCreate, StockUpdate
from app.utils.query_params import SortOrder


def get_stock_profile(db: Session, symbol: str):
    """Get stock basic profile."""
    return db.query(Stock).filter(Stock.symbol == symbol).first()


def get_stock_daily(
    db: Session,
    symbol: str,
    start: date | None = None,
    end: date | None = None,
    sort: SortOrder = "asc",
    min_volume: float | None = None,
):
    """Get daily price series for a symbol."""
    query = db.query(DailyPrice).filter(DailyPrice.symbol == symbol)
    if start is not None:
        query = query.filter(DailyPrice.date >= start)
    if end is not None:
        query = query.filter(DailyPrice.date <= end)
    if min_volume is not None:
        query = query.filter(DailyPrice.volume >= min_volume)
    if sort == "desc":
        return query.order_by(DailyPrice.date.desc()).all()
    return query.order_by(DailyPrice.date.asc()).all()


def get_risk_snapshot(symbol: str) -> dict | None:
    """Get cached risk metrics from Redis if available."""
    return get_json(f"risk:{symbol}")


def create_stock(db: Session, payload: StockCreate):
    item = Stock(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_stock(db: Session, symbol: str, payload: StockUpdate):
    item = db.query(Stock).filter(Stock.symbol == symbol).first()
    if item is None:
        return None
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_stock(db: Session, symbol: str) -> bool:
    item = db.query(Stock).filter(Stock.symbol == symbol).first()
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
