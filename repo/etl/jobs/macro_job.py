from __future__ import annotations

from datetime import date

from etl.fetchers.akshare_client import get_macro_series
from etl.loaders.pg_loader import upsert_macro
from etl.loaders.redis_cache import cache_macro
from etl.transformers.macro import normalize_macro_rows
from etl.utils.dates import date_range
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)

MACRO_CODES = ["CPI", "PPI", "M2", "PMI", "SHIBOR", "TSF"]


def run_macro_job(start: date, end: date) -> int:
    """Run macro job: fetch macro series and store into DB (incremental)."""
    total = 0
    for as_of in date_range(start, end):
        all_rows = []
        for code in MACRO_CODES:
            fetched = get_macro_series(code, as_of, as_of)
            if not fetched:
                continue
            all_rows.extend(fetched)
        rows = normalize_macro_rows(all_rows)
        if not rows:
            LOGGER.info("macro_job empty for %s", as_of)
            continue
        upsert_macro(rows)

        cache_items = [
            {
                "key": row.get("key"),
                "date": row.get("date"),
                "value": row.get("value"),
                "score": row.get("score"),
            }
            for row in rows
        ]
        cache_macro(as_of, {"items": cache_items, "date": as_of.isoformat()})
        total += len(rows)
    return total
