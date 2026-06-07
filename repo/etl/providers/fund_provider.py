from __future__ import annotations

from datetime import date

from etl.providers.base_provider import BaseProvider
from etl.fetchers.fund_holdings_client import get_fund_holdings as _get_fund_holdings


class FundProvider(BaseProvider):
    """基金持仓 Provider。"""

    def get_fund_holdings(self, as_of: date) -> list[dict]:
        result = self._safe_call(_get_fund_holdings, as_of)
        return result or []
