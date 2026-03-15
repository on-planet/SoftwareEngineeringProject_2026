from __future__ import annotations

from datetime import date

from app.services.live_market_service import get_live_risk_series


def get_risk_series(
    symbol: str,
    window: int = 20,
    limit: int = 200,
    end: date | None = None,
    start: date | None = None,
):
    return get_live_risk_series(symbol, window=window, limit=limit, end=end, start=start)
