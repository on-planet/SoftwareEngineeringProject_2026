from __future__ import annotations

from datetime import date
from typing import List

from etl.fetchers.baostock_client import (
    get_daily_prices as bs_get_daily_prices,
    get_financials as bs_get_financials,
    get_index_daily as bs_get_index_daily,
)


def get_index_daily(as_of: date) -> List[dict]:
    """Fetch A-share index daily data for the given date using BaoStock."""
    return bs_get_index_daily(as_of)


def get_daily_prices(symbols, as_of: date) -> List[dict]:
    """Fetch A-share daily prices for the given symbols and date using BaoStock."""
    return bs_get_daily_prices(symbols, as_of)


def get_financials(symbol: str, period: str) -> dict:
    """Fetch financial statements for a symbol and period using BaoStock."""
    return bs_get_financials(symbol, period)
