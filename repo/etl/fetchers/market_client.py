from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import List

from etl.loaders.pg_loader import list_stock_rows
from etl.fetchers.snowball_client import (
    get_daily_prices as sb_get_daily_prices,
    get_financials as sb_get_financials,
    get_index_daily as sb_get_index_daily,
    get_monthly_prices as sb_get_monthly_prices,
    get_stock_basics as sb_get_stock_basics,
    snowball_session,
)
from etl.utils.stock_basics_cache import load_stock_basics_cache, save_stock_basics_cache


@contextmanager
def market_data_session():
    with snowball_session():
        yield


def get_stock_basic(
    symbols: list[str] | None = None,
    *,
    force_refresh: bool = False,
    allow_stale_cache: bool = True,
) -> List[dict]:
    requested = [str(symbol).strip() for symbol in symbols or [] if str(symbol).strip()] or None
    requested_count = len(set(requested or []))

    if not force_refresh:
        cached_rows = load_stock_basics_cache(requested, allow_stale=allow_stale_cache)
        if cached_rows and (requested is None or len(cached_rows) >= requested_count):
            return cached_rows

        db_rows = list_stock_rows()
        if db_rows:
            save_stock_basics_cache(db_rows)
            normalized_db_rows = load_stock_basics_cache(requested, allow_stale=True)
            if requested:
                if len(normalized_db_rows) >= requested_count:
                    return normalized_db_rows
            else:
                return normalized_db_rows or db_rows

    rows = sb_get_stock_basics(requested)
    if rows:
        save_stock_basics_cache(rows, merge=bool(requested))
    return rows


def get_index_daily(as_of: date) -> List[dict]:
    return sb_get_index_daily(as_of)


def get_daily_prices(symbols, as_of: date, *, workers: int | None = None) -> List[dict]:
    return sb_get_daily_prices(symbols, as_of, workers=workers)


def get_monthly_prices(symbols, as_of: date) -> List[dict]:
    return sb_get_monthly_prices(symbols, as_of)


def get_financials(symbol: str, period: str) -> dict:
    return sb_get_financials(symbol, period)
