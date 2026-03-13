from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.daily_prices import DailyPrice
from etl.transformers.indicators import calc_max_drawdown, calc_volatility


def get_risk_snapshot(db: Session, symbol: str, window: int = 60) -> dict | None:
    """Compute risk snapshot for symbol (max drawdown + volatility)."""
    key = f"risk:{symbol}"
    cached = get_json(key)
    if cached:
        payload = dict(cached)
        payload["cache_hit"] = True
        return payload

    latest_date = (
        db.query(func.max(DailyPrice.date))
        .filter(DailyPrice.symbol == symbol)
        .scalar()
    )
    if latest_date is None:
        return None
    rows = (
        db.query(DailyPrice)
        .filter(DailyPrice.symbol == symbol, DailyPrice.date <= latest_date)
        .order_by(DailyPrice.date.desc())
        .limit(window)
        .all()[::-1]
    )
    if not rows:
        return None
    closes = [float(row.close or 0) for row in rows]
    returns = [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
        if closes[i - 1]
    ]
    payload = {
        "symbol": symbol,
        "max_drawdown": calc_max_drawdown(closes),
        "volatility": calc_volatility(returns),
        "as_of": latest_date,
    }
    set_json(key, payload)
    response = dict(payload)
    response["cache_hit"] = False
    return response
