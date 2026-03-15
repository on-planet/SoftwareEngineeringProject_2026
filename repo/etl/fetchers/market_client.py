from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import List

from etl.fetchers.snowball_client import (
    get_daily_prices as sb_get_daily_prices,
    get_financials as sb_get_financials,
    get_index_daily as sb_get_index_daily,
    get_monthly_prices as sb_get_monthly_prices,
    get_stock_basic as sb_get_stock_basic,
    snowball_session,
)


@contextmanager
def market_data_session():
    with snowball_session():
        yield


def get_stock_basic() -> List[dict]:
    return sb_get_stock_basic()


def get_index_daily(as_of: date) -> List[dict]:
    return sb_get_index_daily(as_of)


def get_daily_prices(symbols, as_of: date) -> List[dict]:
    return sb_get_daily_prices(symbols, as_of)


def get_monthly_prices(symbols, as_of: date) -> List[dict]:
    return sb_get_monthly_prices(symbols, as_of)


def get_financials(symbol: str, period: str) -> dict:
    return sb_get_financials(symbol, period)
