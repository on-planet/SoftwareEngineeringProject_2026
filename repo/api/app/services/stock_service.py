from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.stocks import Stock
from app.schemas.stock import StockCreate, StockUpdate
from app.services.live_market_service import get_live_stock_daily, get_live_stock_profile, list_live_stocks


def list_stocks(
    *,
    market: str | None = None,
    keyword: str | None = None,
    limit: int = 100,
    offset: int = 0,
    sort: str = "asc",
):
    return list_live_stocks(market=market, keyword=keyword, limit=limit, offset=offset, sort=sort)


def get_stock_profile(symbol: str):
    return get_live_stock_profile(symbol)


def get_stock_daily(
    symbol: str,
    start: date | None = None,
    end: date | None = None,
    sort: str = "asc",
    min_volume: float | None = None,
):
    return get_live_stock_daily(symbol, start=start, end=end, sort=sort, min_volume=min_volume)


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
