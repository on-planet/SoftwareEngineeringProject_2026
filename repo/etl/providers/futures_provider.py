from __future__ import annotations

from datetime import date

from etl.providers.base_provider import BaseProvider
from etl.fetchers.futures_client import (
    get_futures_daily as _get_futures_daily,
    get_futures_history as _get_futures_history,
    get_futures_weekly as _get_futures_weekly,
    SUPPORTED_FUTURES_SYMBOLS,
)


class FuturesProvider(BaseProvider):
    """期货数据 Provider：上期所日/周数据。"""

    def get_futures_daily(self, as_of: date) -> list[dict]:
        result = self._safe_call(_get_futures_daily, as_of)
        return result or []

    def get_futures_weekly(self, as_of: date) -> list[dict]:
        result = self._safe_call(_get_futures_weekly, as_of)
        return result or []

    def get_futures_history(
        self,
        symbol: str,
        *,
        start: date | None = None,
        end: date | None = None,
        limit: int = 480,
    ) -> list[dict]:
        result = self._safe_call(_get_futures_history, symbol, start=start, end=end, limit=limit)
        return result or []

    def supported_symbols(self) -> tuple[str, ...]:
        return SUPPORTED_FUTURES_SYMBOLS
