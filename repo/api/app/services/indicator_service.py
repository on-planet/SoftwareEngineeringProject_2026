from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.daily_prices import DailyPrice
from app.schemas.indicators import IndicatorPoint
from etl.transformers.indicators import calc_ma, calc_rsi


def _cache_key(symbol: str, indicator: str, window: int, limit: int, start: date | None, end: date | None) -> str:
    start_key = start.isoformat() if start else "none"
    end_key = end.isoformat() if end else "none"
    return f"indicators:{symbol}:{indicator}:{window}:{limit}:{start_key}:{end_key}"


def _select_prices(db: Session, symbol: str, end: date | None, limit: int, start: date | None = None):
    query = db.query(DailyPrice).filter(DailyPrice.symbol == symbol)
    if end is not None:
        query = query.filter(DailyPrice.date <= end)
    if start is not None:
        query = query.filter(DailyPrice.date >= start)
    return (
        query.order_by(DailyPrice.date.desc())
        .limit(limit)
        .all()[::-1]
    )


def get_indicator_series(
    db: Session,
    symbol: str,
    indicator: str,
    window: int = 14,
    limit: int = 200,
    end: date | None = None,
    start: date | None = None,
):
    """Compute indicator series based on daily close prices."""
    cache_key = _cache_key(symbol, indicator, window, limit, start, end)
    cached = get_json(cache_key)
    if isinstance(cached, list):
        return cached, True

    rows = _select_prices(db, symbol, end, limit, start)
    if not rows:
        return [], False
    closes = [float(row.close or 0) for row in rows]
    if indicator == "ma":
        values = calc_ma(closes, window)
    elif indicator == "rsi":
        values = calc_rsi(closes, window)
    else:
        raise ValueError("Unsupported indicator")
    items = [
        IndicatorPoint(date=row.date, value=float(value))
        for row, value in zip(rows, values)
    ]
    set_json(cache_key, [item.dict() for item in items])
    return items, False
