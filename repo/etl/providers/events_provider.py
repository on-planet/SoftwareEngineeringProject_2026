from __future__ import annotations

from datetime import date

from etl.providers.base_provider import BaseProvider
from etl.fetchers.events_client import (
    get_events as _get_events,
    get_buyback as _get_buyback,
    get_insider_trade as _get_insider_trade,
)


class EventsProvider(BaseProvider):
    """公司事件 Provider：公告、回购、内幕交易等。"""

    def get_events(self, as_of: date) -> list[dict]:
        result = self._safe_call(_get_events, as_of)
        return result or []

    def get_buyback(self, as_of: date) -> list[dict]:
        result = self._safe_call(_get_buyback, as_of)
        return result or []

    def get_insider_trade(self, as_of: date) -> list[dict]:
        result = self._safe_call(_get_insider_trade, as_of)
        return result or []
