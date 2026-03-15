from __future__ import annotations

from app.services.live_market_service import get_live_stock_research


def get_stock_research(symbol: str, *, report_limit: int = 10, forecast_limit: int = 10) -> dict:
    return get_live_stock_research(symbol, report_limit=report_limit, forecast_limit=forecast_limit)
