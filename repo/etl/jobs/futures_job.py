from __future__ import annotations

from datetime import date

from etl.fetchers.futures_client import get_futures_daily
from etl.loaders.pg_loader import upsert_futures_prices
from etl.utils.dates import date_range
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


def run_futures_job(start: date, end: date) -> int:
    """Run futures job: fetch major futures daily data and store into DB."""
    total = 0
    for as_of in date_range(start, end):
        rows = get_futures_daily(as_of)
        if not rows:
            LOGGER.info("futures_job empty for %s", as_of)
            continue
        total += upsert_futures_prices(rows)
    return total
