from __future__ import annotations

from app.services.live_market_service import get_live_risk_snapshot


def get_risk_snapshot(symbol: str, window: int = 60) -> dict | None:
    return get_live_risk_snapshot(symbol, window=window)
