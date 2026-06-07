from __future__ import annotations

from datetime import date

from etl.providers.base_provider import BaseProvider
from etl.fetchers.akshare_macro_client import (
    fetch_all_akshare_macro_rows as _fetch_all_akshare_macro_rows,
    fetch_akshare_series_rows as _fetch_akshare_series_rows,
    is_akshare_macro_key as _is_akshare_macro_key,
)
from etl.fetchers.worldbank_client import get_indicator_series as _get_indicator_series


class MacroProvider(BaseProvider):
    """宏观经济数据 Provider：国内宏观指标 + 世界银行开放数据。"""

    def fetch_all_akshare_macro_rows(
        self,
        *,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict]:
        return _fetch_all_akshare_macro_rows(start=start, end=end)

    def fetch_akshare_series_rows(
        self,
        key: str,
        start: date | None = None,
        end: date | None = None,
    ) -> list[dict]:
        return _fetch_akshare_series_rows(key, start=start, end=end)

    def is_akshare_macro_key(self, key: str) -> bool:
        return _is_akshare_macro_key(key)

    def get_indicator_series(
        self,
        country: str,
        indicator: str,
        start: date,
        end: date,
    ) -> list[dict]:
        result = self._safe_call(_get_indicator_series, country, indicator, start, end)
        return result or []
