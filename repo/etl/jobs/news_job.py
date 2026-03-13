from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import os
import time

from etl.fetchers.news_client import get_news
from etl.loaders.pg_loader import upsert_news
from etl.utils.dates import date_range
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


def run_news_job(start: date, end: date) -> int:
    """Run news job: fetch news, calculate sentiment, store into DB (incremental)."""
    total = 0
    job_start = time.perf_counter()
    dates = list(date_range(start, end))
    max_workers = int(os.getenv("NEWS_JOB_WORKERS", "4"))

    fetch_results: dict[date, tuple[list[dict], float]] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(get_news, as_of): as_of
            for as_of in dates
        }
        for future in as_completed(future_map):
            as_of = future_map[future]
            fetch_start = time.perf_counter()
            try:
                rows = future.result()
            except Exception as exc:
                LOGGER.warning("news_job fetch failed for %s: %s", as_of, exc)
                rows = []
            fetch_cost = time.perf_counter() - fetch_start
            fetch_results[as_of] = (rows, fetch_cost)

    for as_of in dates:
        rows, fetch_cost = fetch_results.get(as_of, ([], 0.0))
        if not rows:
            LOGGER.info("news_job empty for %s (fetch %.2fs)", as_of, fetch_cost)
            continue
        write_start = time.perf_counter()
        written = upsert_news(rows)
        write_cost = time.perf_counter() - write_start
        total += written
        LOGGER.info(
            "news_job %s rows=%s fetch=%.2fs write=%.2fs",
            as_of,
            len(rows),
            fetch_cost,
            write_cost,
        )

    LOGGER.info(
        "news_job total=%s days=%s cost=%.2fs workers=%s",
        total,
        len(dates),
        time.perf_counter() - job_start,
        max_workers,
    )
    return total
