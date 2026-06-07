from __future__ import annotations

from datetime import datetime

from etl.providers.base_provider import BaseProvider
from etl.fetchers.akshare_reference_client import (
    fetch_bond_market_quote_rows as _fetch_bond_market_quote_rows,
    fetch_bond_market_trade_rows as _fetch_bond_market_trade_rows,
    fetch_fx_spot_quote_rows as _fetch_fx_spot_quote_rows,
    fetch_fx_swap_quote_rows as _fetch_fx_swap_quote_rows,
    fetch_fx_pair_quote_rows as _fetch_fx_pair_quote_rows,
    fetch_stock_institute_hold_rows as _fetch_stock_institute_hold_rows,
    fetch_stock_report_disclosure_rows as _fetch_stock_report_disclosure_rows,
)


class ReferenceProvider(BaseProvider):
    """参考数据 Provider：债券、外汇、机构持股、财报披露等。"""

    def fetch_bond_market_quote_rows(self, *, as_of: datetime | None = None) -> list[dict]:
        return _fetch_bond_market_quote_rows(as_of=as_of)

    def fetch_bond_market_trade_rows(self, *, as_of: datetime | None = None) -> list[dict]:
        return _fetch_bond_market_trade_rows(as_of=as_of)

    def fetch_fx_spot_quote_rows(self, *, as_of: datetime | None = None) -> list[dict]:
        return _fetch_fx_spot_quote_rows(as_of=as_of)

    def fetch_fx_swap_quote_rows(self, *, as_of: datetime | None = None) -> list[dict]:
        return _fetch_fx_swap_quote_rows(as_of=as_of)

    def fetch_fx_pair_quote_rows(self, *, as_of: datetime | None = None) -> list[dict]:
        return _fetch_fx_pair_quote_rows(as_of=as_of)

    def fetch_stock_institute_hold_rows(
        self,
        quarter: str,
        *,
        as_of: datetime | None = None,
    ) -> list[dict]:
        return _fetch_stock_institute_hold_rows(quarter, as_of=as_of)

    def fetch_stock_report_disclosure_rows(
        self,
        market: str,
        period: str,
        *,
        as_of: datetime | None = None,
    ) -> list[dict]:
        return _fetch_stock_report_disclosure_rows(market, period, as_of=as_of)
