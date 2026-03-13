from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.daily_prices import DailyPrice
from app.schemas.kline import KlinePoint


def _select_index_prices(db: Session, symbol: str, end: date | None, limit: int):
    query = db.query(DailyPrice).filter(DailyPrice.symbol == symbol)
    if end is not None:
        query = query.filter(DailyPrice.date <= end)
    return (
        query.order_by(DailyPrice.date.desc())
        .limit(limit)
        .all()[::-1]
    )


def get_index_kline(
    db: Session,
    symbol: str,
    limit: int = 200,
    end: date | None = None,
    start: date | None = None,
):
    rows = _select_index_prices(db, symbol, end, limit)
    if start is not None:
        rows = [row for row in rows if row.date >= start]
    return [
        KlinePoint(
            date=row.date,
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
        )
        for row in rows
    ]
