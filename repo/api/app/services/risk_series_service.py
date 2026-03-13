from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.daily_prices import DailyPrice
from app.schemas.risk_series import RiskPoint
from etl.transformers.indicators import calc_max_drawdown, calc_volatility


def _cache_key(symbol: str, window: int, limit: int, start: date | None, end: date | None) -> str:
    start_key = start.isoformat() if start else "none"
    end_key = end.isoformat() if end else "none"
    return f"risk_series:{symbol}:{window}:{limit}:{start_key}:{end_key}"


def get_risk_series(
    db: Session,
    symbol: str,
    window: int = 20,
    limit: int = 200,
    end: date | None = None,
    start: date | None = None,
):
    cache_key = _cache_key(symbol, window, limit, start, end)
    cached = get_json(cache_key)
    if isinstance(cached, list):
        return cached, True

    query = db.query(DailyPrice).filter(DailyPrice.symbol == symbol)
    if end is not None:
        query = query.filter(DailyPrice.date <= end)
    if start is not None:
        query = query.filter(DailyPrice.date >= start)
    rows = (
        query.order_by(DailyPrice.date.desc())
        .limit(limit)
        .all()[::-1]
    )
    if not rows:
        return [], False
    closes = [float(row.close or 0) for row in rows]
    returns = [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
        if closes[i - 1]
    ]
    points: list[RiskPoint] = []
    for idx in range(len(rows)):
        window_start = max(0, idx - window + 1)
        window_prices = closes[window_start : idx + 1]
        window_returns = returns[window_start:idx] if idx > 0 else []
        points.append(
            RiskPoint(
                date=rows[idx].date,
                max_drawdown=calc_max_drawdown(window_prices),
                volatility=calc_volatility(window_returns),
            )
        )
    set_json(cache_key, [point.dict() for point in points])
    return points, False
