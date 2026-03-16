from __future__ import annotations

from datetime import date

from etl.fetchers.futures_client import get_futures_daily, get_futures_weekly
from etl.loaders.pg_loader import upsert_futures_prices, upsert_futures_weekly_prices
from etl.utils.dates import date_range
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


def run_futures_job(start: date, end: date) -> int:
    """Run futures job: fetch SHFE daily and weekly futures data and store into DB."""
    total = 0
    for as_of in date_range(start, end):
        rows = get_futures_daily(as_of)
        if not rows:
            LOGGER.info("futures_job empty for %s", as_of)
        else:
            total += upsert_futures_prices(rows)
    total += run_futures_weekly_job(start, end)
    return total


def _normalize_weekly_as_of(as_of: date) -> date:
    return as_of.fromordinal(as_of.toordinal() - ((as_of.weekday() - 4) % 7))


def weekly_snapshot_dates(start: date, end: date) -> list[date]:
    if start > end:
        return []
    first = start
    while first.weekday() != 4:
        first = first.fromordinal(first.toordinal() + 1)
    last = _normalize_weekly_as_of(end)
    if first > last:
        return []
    output: list[date] = []
    current = first
    while current <= last:
        output.append(current)
        current = current.fromordinal(current.toordinal() + 7)
    return output


def run_futures_weekly_job(start: date, end: date) -> int:
    total = 0
    for week_end in weekly_snapshot_dates(start, end):
        weekly_rows = get_futures_weekly(week_end)
        if not weekly_rows:
            LOGGER.info("futures_job weekly empty for %s", week_end)
            continue
        total += upsert_futures_weekly_prices(weekly_rows)
    return total
