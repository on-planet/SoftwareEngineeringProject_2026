from __future__ import annotations

from datetime import date

from etl.utils.env import load_project_env

load_project_env()

from etl.fetchers.market_client import get_stock_basic as _get_stock_basic
from etl.fetchers.snowball_client import (
    get_daily_history as _get_daily_history,
    get_kline_history as _get_kline_history,
    get_recent_financials as _get_recent_financials,
    get_stock_earning_forecasts as _get_stock_earning_forecasts,
    get_stock_pankou as _get_stock_pankou,
    get_stock_quote as _get_stock_quote,
    get_stock_quote_detail as _get_stock_quote_detail,
    get_stock_reports as _get_stock_reports,
    market_from_symbol as _market_from_symbol,
    normalize_index_symbol as _normalize_index_symbol,
)
from etl.utils.stock_basics_cache import load_stock_basics_cache as _load_stock_basics_cache


def get_cached_stock_basic(
    symbols: list[str] | None = None,
    *,
    force_refresh: bool = False,
    allow_stale_cache: bool = True,
) -> list[dict]:
    return _get_stock_basic(symbols, force_refresh=force_refresh, allow_stale_cache=allow_stale_cache)


def load_stock_basics_cache(
    symbols: list[str] | None = None,
    *,
    allow_stale: bool = True,
) -> list[dict]:
    return _load_stock_basics_cache(symbols, allow_stale=allow_stale)


def get_daily_history(symbol: str, *, count: int = 240, as_of: date | None = None) -> list[dict]:
    return _get_daily_history(symbol, count=count, as_of=as_of)


def get_kline_history(
    symbol: str,
    *,
    period: str = "day",
    count: int = 240,
    as_of: date | None = None,
    is_index: bool = False,
) -> list[dict]:
    return _get_kline_history(symbol, period=period, count=count, as_of=as_of, is_index=is_index)


def get_recent_financials(symbol: str, *, count: int = 8) -> list[dict]:
    return _get_recent_financials(symbol, count=count)


def get_stock_quote(symbol: str) -> dict:
    return _get_stock_quote(symbol)


def get_stock_quote_detail(symbol: str) -> dict:
    return _get_stock_quote_detail(symbol)


def get_stock_pankou(symbol: str) -> dict:
    return _get_stock_pankou(symbol)


def get_stock_reports(symbol: str, *, limit: int = 10) -> list[dict]:
    return _get_stock_reports(symbol, limit=limit)


def get_stock_earning_forecasts(symbol: str, *, limit: int = 10) -> list[dict]:
    return _get_stock_earning_forecasts(symbol, limit=limit)


def normalize_index_symbol(symbol: str) -> str:
    return _normalize_index_symbol(symbol)


def market_from_symbol(symbol: str) -> str:
    return _market_from_symbol(symbol)
