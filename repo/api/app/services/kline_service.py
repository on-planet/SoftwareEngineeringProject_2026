from __future__ import annotations

from datetime import date
from typing import Literal

from app.services.live_market_service import get_live_kline

KlinePeriod = Literal["day", "week", "month", "quarter", "year"]


def get_stock_kline(
    symbol: str,
    *,
    period: KlinePeriod = "day",
    limit: int = 200,
    end: date | None = None,
    start: date | None = None,
):
    return get_live_kline(symbol, period=period, limit=limit, end=end, start=start, is_index=False)


def get_index_kline(
    symbol: str,
    *,
    period: KlinePeriod = "day",
    limit: int = 200,
    end: date | None = None,
    start: date | None = None,
):
    return get_live_kline(symbol, period=period, limit=limit, end=end, start=start, is_index=True)
