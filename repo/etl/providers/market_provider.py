from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from typing import Iterable

from etl.fetchers.market_client import get_stock_basic as _get_enriched_stock_basic
from etl.fetchers.snowball_client import (
    get_daily_history as _get_daily_history,
    get_daily_prices as _get_daily_prices,
    get_financials as _get_financials,
    get_index_daily as _get_index_daily,
    get_kline_history as _get_kline_history,
    get_recent_financials as _get_recent_financials,
    get_stock_earning_forecasts as _get_stock_earning_forecasts,
    get_stock_pankou as _get_stock_pankou,
    get_stock_quote as _get_stock_quote,
    get_stock_quote_detail as _get_stock_quote_detail,
    get_stock_quotes as _get_stock_quotes,
    get_stock_reports as _get_stock_reports,
    index_market as _index_market,
    index_name as _index_name,
    market_from_symbol as _market_from_symbol,
    normalize_index_symbol as _normalize_index_symbol,
    normalize_symbol as _normalize_symbol,
    snowball_session as _snowball_session,
    supported_index_specs as _supported_index_specs,
)
from etl.providers.base_provider import BaseProvider


class MarketProvider(BaseProvider):
    """Market data provider backed by Snowball fetchers."""

    def get_stock_basic(
        self,
        symbols: list[str] | None = None,
        *,
        force_refresh: bool = False,
        allow_stale_cache: bool = True,
    ) -> list[dict]:
        return _get_enriched_stock_basic(
            symbols,
            force_refresh=force_refresh,
            allow_stale_cache=allow_stale_cache,
        )

    def normalize_symbol(self, symbol: str) -> str:
        return _normalize_symbol(symbol)

    def normalize_index_symbol(self, symbol: str) -> str:
        return _normalize_index_symbol(symbol)

    def market_from_symbol(self, symbol: str) -> str:
        return _market_from_symbol(symbol)

    def get_stock_quote(self, symbol: str) -> dict | None:
        return self._safe_call(_get_stock_quote, symbol)

    def get_stock_quote_detail(self, symbol: str) -> dict | None:
        return self._safe_call(_get_stock_quote_detail, symbol)

    def get_stock_pankou(self, symbol: str) -> dict | None:
        return self._safe_call(_get_stock_pankou, symbol)

    def get_daily_history(
        self,
        symbol: str,
        *,
        count: int = 480,
        as_of: date | None = None,
    ) -> list[dict]:
        result = self._safe_call(_get_daily_history, symbol, count=count, as_of=as_of)
        return result or []

    def get_kline_history(
        self,
        symbol: str,
        *,
        period: str = "day",
        count: int = 240,
        as_of: date | None = None,
        is_index: bool = False,
    ) -> list[dict]:
        result = self._safe_call(
            _get_kline_history,
            symbol,
            period=period,
            count=count,
            as_of=as_of,
            is_index=is_index,
        )
        return result or []

    def get_recent_financials(
        self,
        symbol: str,
        *,
        count: int = 8,
        as_of: date | None = None,
    ) -> list[dict]:
        result = self._safe_call(_get_recent_financials, symbol, count=count, as_of=as_of)
        return result or []

    def get_stock_reports(self, symbol: str, *, limit: int = 10) -> list[dict]:
        result = self._safe_call(_get_stock_reports, symbol, limit=limit)
        return result or []

    def get_stock_earning_forecasts(self, symbol: str, *, limit: int = 10) -> list[dict]:
        result = self._safe_call(_get_stock_earning_forecasts, symbol, limit=limit)
        return result or []

    def get_daily_prices(
        self,
        symbols: Iterable[str],
        as_of: date,
        *,
        workers: int | None = None,
    ) -> list[dict]:
        return _get_daily_prices(symbols, as_of, workers=workers)

    def get_index_daily(self, as_of: date) -> list[dict]:
        return _get_index_daily(as_of)

    def get_financials(self, symbol: str, period: str) -> dict:
        return _get_financials(symbol, period)

    def get_stock_quotes(self, symbols: Iterable[str] | None = None) -> list[dict]:
        result = self._safe_call(_get_stock_quotes, symbols)
        return result or []

    def index_name(self, symbol: str) -> str:
        return _index_name(symbol)

    def index_market(self, symbol: str) -> str:
        return _index_market(symbol)

    def supported_index_specs(self) -> list[dict]:
        return _supported_index_specs()

    @contextmanager
    def session(self):
        with _snowball_session():
            yield
