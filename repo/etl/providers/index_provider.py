from __future__ import annotations

from datetime import date

from etl.providers.base_provider import BaseProvider
from etl.fetchers.index_constituent_client import get_index_constituents as _get_index_constituents
from etl.fetchers.hk_index_client import (
    get_hk_index_constituents as _get_hk_index_constituents,
    supported_hk_index_symbols as _supported_hk_index_symbols,
)


class IndexProvider(BaseProvider):
    """指数成分 Provider：A股指数 + 港股指数成分股。"""

    def get_index_constituents(self, index_symbol: str, as_of: date) -> list[dict]:
        result = self._safe_call(_get_index_constituents, index_symbol, as_of)
        return result or []

    def get_hk_index_constituents(self, symbol: str) -> list[dict]:
        result = self._safe_call(_get_hk_index_constituents, symbol)
        return result or []

    def supported_hk_index_symbols(self) -> list[str]:
        return _supported_hk_index_symbols()
