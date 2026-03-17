from __future__ import annotations

from datetime import date

from app.services.live_market_service import get_live_indicator_series

AVAILABLE_INDICATORS = (
    "ma",
    "sma",
    "ema",
    "wma",
    "rsi",
    "macd",
    "boll",
    "kdj",
    "atr",
    "cci",
    "wr",
    "obv",
    "roc",
    "mom",
    "adx",
    "mfi",
)


def get_indicator_series(
    symbol: str,
    indicator: str,
    window: int = 14,
    limit: int = 200,
    end: date | None = None,
    start: date | None = None,
):
    return get_live_indicator_series(symbol, indicator, window=window, limit=limit, end=end, start=start)
