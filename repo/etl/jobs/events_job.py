from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import os

from etl.fetchers.events_client import get_events, get_buyback, get_insider_trade
from etl.loaders.pg_loader import upsert_events, upsert_buyback, upsert_insider_trade
from etl.loaders.redis_cache import cache_events
from etl.utils.dates import date_range
from etl.utils.logging import get_logger
from etl.utils.normalize import ensure_required

LOGGER = get_logger(__name__)


def _fetch_event_day(as_of: date) -> tuple[list[dict], list[dict], list[dict]]:
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="events_day") as executor:
        event_future = executor.submit(get_events, as_of)
        buyback_future = executor.submit(get_buyback, as_of)
        insider_future = executor.submit(get_insider_trade, as_of)
        events_rows = ensure_required(event_future.result(), ["symbol", "type", "title", "date"], "events.events")
        buyback_rows = ensure_required(buyback_future.result(), ["symbol", "date", "amount"], "events.buyback")
        insider_rows = ensure_required(insider_future.result(), ["symbol", "date", "type", "shares"], "events.insider")
        return events_rows, buyback_rows, insider_rows


def run_events_job(start: date, end: date) -> int:
    """Run events job: fetch events and store into DB (incremental)."""
    total = 0
    dates = list(date_range(start, end))
    max_workers = int(os.getenv("EVENTS_JOB_WORKERS", "4"))

    fetch_results: dict[date, tuple[list[dict], list[dict], list[dict]]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_fetch_event_day, as_of): as_of for as_of in dates}
        for future in as_completed(future_map):
            as_of = future_map[future]
            try:
                fetch_results[as_of] = future.result()
            except Exception as exc:
                LOGGER.warning("events_job fetch failed for %s: %s", as_of, exc)
                fetch_results[as_of] = ([], [], [])

    for as_of in dates:
        events_rows, buyback_rows, insider_rows = fetch_results.get(as_of, ([], [], []))

        if events_rows:
            upsert_events(events_rows)
        if buyback_rows:
            upsert_buyback(buyback_rows)
        if insider_rows:
            upsert_insider_trade(insider_rows)

        if not (events_rows or buyback_rows or insider_rows):
            LOGGER.info("events_job empty for %s", as_of)
            continue

        cache_events(
            as_of,
            {
                "items": events_rows,
                "buyback": buyback_rows,
                "insider": insider_rows,
                "date": as_of.isoformat(),
            },
        )

        total += len(events_rows) + len(buyback_rows) + len(insider_rows)

    return total
