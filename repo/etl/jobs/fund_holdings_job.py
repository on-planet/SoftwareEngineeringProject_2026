from __future__ import annotations

from datetime import date

from etl.providers import get_provider

_provider = get_provider()
from etl.loaders.pg_loader import upsert_fund_holdings
from etl.utils.dates import date_range
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


def run_fund_holdings_job(start: date, end: date) -> int:
    """Run fund holdings job."""
    total = 0
    for as_of in date_range(start, end):
        rows = _provider.fund.get_fund_holdings(as_of)
        if not rows:
            LOGGER.info("fund_holdings_job empty for %s", as_of)
            continue
        total += upsert_fund_holdings(rows)
    return total
