from __future__ import annotations

from datetime import date
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.daily_prices import DailyPrice
from etl.loaders.redis_cache import cache_risk_series, cache_indicator
from etl.transformers.indicators import calc_max_drawdown, calc_volatility, calc_ma, calc_rsi


def _select_prices(db: Session, symbol: str, end: date | None, limit: int) -> List[DailyPrice]:
    query = db.query(DailyPrice).filter(DailyPrice.symbol == symbol)
    if end is not None:
        query = query.filter(DailyPrice.date <= end)
    return (
        query.order_by(DailyPrice.date.desc())
        .limit(limit)
        .all()[::-1]
    )


def write_risk_series_cache(db: Session, symbol: str, window: int = 20, limit: int = 200, end: date | None = None) -> None:
    rows = _select_prices(db, symbol, end, limit)
    if not rows:
        return
    closes = [float(row.close or 0) for row in rows]
    returns = [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
        if closes[i - 1]
    ]
    items = []
    for idx in range(len(rows)):
        start = max(0, idx - window + 1)
        window_prices = closes[start : idx + 1]
        window_returns = returns[start:idx] if idx > 0 else []
        items.append(
            {
                "date": rows[idx].date,
                "max_drawdown": calc_max_drawdown(window_prices),
                "volatility": calc_volatility(window_returns),
            }
        )
    cache_risk_series(symbol, {"symbol": symbol, "items": items})


def write_indicator_cache(
    db: Session,
    symbol: str,
    indicator: str,
    window: int = 14,
    limit: int = 200,
    end: date | None = None,
) -> None:
    rows = _select_prices(db, symbol, end, limit)
    if not rows:
        return
    closes = [float(row.close or 0) for row in rows]
    if indicator == "ma":
        values = calc_ma(closes, window)
    elif indicator == "rsi":
        values = calc_rsi(closes, window)
    else:
        return
    items = [
        {"date": row.date, "value": float(value)}
        for row, value in zip(rows, values)
    ]
    cache_indicator(symbol, indicator, {"symbol": symbol, "indicator": indicator, "window": window, "items": items})


def list_symbols(db: Session, limit: int = 200) -> list[str]:
    rows = db.query(DailyPrice.symbol).group_by(DailyPrice.symbol).limit(limit).all()
    return [row[0] for row in rows]
