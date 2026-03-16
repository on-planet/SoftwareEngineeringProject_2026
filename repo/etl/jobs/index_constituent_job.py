from __future__ import annotations

from datetime import date

from etl.fetchers.index_constituent_client import get_index_constituents
from etl.loaders.pg_loader import upsert_index_constituents
from etl.utils.dates import date_range
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)

INDEX_SYMBOLS = ["000016.SH", "000300.SH", "000688.SH", "899050.BJ"]


def run_index_constituent_job(start: date, end: date) -> int:
    """Run index constituent job."""
    total = 0
    for as_of in date_range(start, end):
        batch = []
        for index_symbol in INDEX_SYMBOLS:
            batch.extend(get_index_constituents(index_symbol, as_of))
        if not batch:
            LOGGER.info("index_constituent_job empty for %s", as_of)
            continue
        total += upsert_index_constituents(batch)
    return total
