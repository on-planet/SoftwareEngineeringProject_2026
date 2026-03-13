from __future__ import annotations

from typing import List

from etl.fetchers.baostock_client import get_stock_basic as bs_get_stock_basic


def get_stock_basic() -> List[dict]:
    """Fetch stock basic list using BaoStock."""
    return bs_get_stock_basic()
