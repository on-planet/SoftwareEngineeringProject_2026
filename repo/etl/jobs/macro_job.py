from __future__ import annotations

import os
from datetime import date

from etl.fetchers.worldbank_client import get_indicator_series
from etl.loaders.pg_loader import count_latest_macro_rows, list_latest_macro_rows, upsert_macro
from etl.loaders.redis_cache import cache_macro
from etl.transformers.macro import normalize_macro_rows
from etl.utils.logging import get_logger
from etl.utils.state import get_job_state, update_job_state

LOGGER = get_logger(__name__)
MACRO_REFRESH_DAYS = max(1, int(os.getenv("MACRO_REFRESH_DAYS", "7")))
MACRO_REFRESH_STATE_KEY = "macro_remote_refresh"

WORLD_BANK_INDICATORS = {
    "GDP": "NY.GDP.MKTP.CD",
    "CPI": "FP.CPI.TOTL.ZG",
    "UNEMP": "SL.UEM.TOTL.ZS",
    "TRADE": "NE.TRD.GNFS.ZS",
}

WORLD_BANK_COUNTRIES = [
    "USA",
    "CHN",
    "JPN",
    "DEU",
    "FRA",
    "GBR",
    "ITA",
    "CAN",
    "AUS",
    "KOR",
    "IND",
    "BRA",
    "RUS",
    "MEX",
    "IDN",
    "TUR",
    "SAU",
    "ZAF",
    "ARG",
    "EUU",
]
EXPECTED_MACRO_KEY_COUNT = len(WORLD_BANK_INDICATORS) * len(WORLD_BANK_COUNTRIES)
MACRO_MIN_KEY_COUNT = max(20, int(os.getenv("MACRO_MIN_KEY_COUNT", str(int(EXPECTED_MACRO_KEY_COUNT * 0.75)))))


def macro_snapshot_is_healthy(min_key_count: int | None = None) -> bool:
    required = MACRO_MIN_KEY_COUNT if min_key_count is None else max(1, min_key_count)
    current = count_latest_macro_rows()
    if current < required:
        LOGGER.info(
            "macro snapshot incomplete: latest_key_count=%s required=%s expected=%s",
            current,
            required,
            EXPECTED_MACRO_KEY_COUNT,
        )
        return False
    return True


def _cache_latest_macro_rows() -> int:
    rows = list_latest_macro_rows()
    if not rows:
        return 0
    latest_date = max(
        (row.get("date") for row in rows if isinstance(row.get("date"), date)),
        default=None,
    )
    if latest_date is None:
        return 0
    cache_macro(latest_date, {"items": rows, "date": latest_date.isoformat()})
    return len(rows)


def run_macro_job(start: date, end: date) -> int:
    """Run macro job: fetch World Bank indicators and store into DB."""
    remote_state = get_job_state(MACRO_REFRESH_STATE_KEY)
    if remote_state.last_success_date is not None:
        age_days = (end - remote_state.last_success_date).days
        if age_days < MACRO_REFRESH_DAYS and macro_snapshot_is_healthy():
            cached_count = _cache_latest_macro_rows()
            LOGGER.info(
                "macro_job skipped remote refresh for %s to %s; last_remote_refresh=%s refresh_days=%s cached_items=%s",
                start,
                end,
                remote_state.last_success_date,
                MACRO_REFRESH_DAYS,
                cached_count,
            )
            return 0
        if age_days < MACRO_REFRESH_DAYS:
            LOGGER.info(
                "macro_job forcing remote refresh because snapshot coverage is incomplete; last_remote_refresh=%s",
                remote_state.last_success_date,
            )

    total = 0
    wb_start = date(max(1960, start.year - 10), 1, 1)
    wb_end = date(end.year, 12, 31)
    latest_rows_by_key: dict[str, dict] = {}

    for country in WORLD_BANK_COUNTRIES:
        for name, indicator in WORLD_BANK_INDICATORS.items():
            fetched = get_indicator_series(country, indicator, wb_start, wb_end)
            if not fetched:
                continue
            for row in fetched:
                row["key"] = f"{name}:{country}"
            rows = normalize_macro_rows(fetched)
            if not rows:
                continue
            upsert_macro(rows)
            total += len(rows)
            series_key = f"{name}:{country}"
            latest_rows_by_key[series_key] = max(rows, key=lambda item: item.get("date") or date.min)

    if total == 0:
        LOGGER.info("macro_job empty for %s to %s", start, end)
        return total

    cache_items = sorted(
        latest_rows_by_key.values(),
        key=lambda item: str(item.get("key") or ""),
    )

    if cache_items:
        latest_date = max(
            (item.get("date") for item in cache_items if isinstance(item.get("date"), date)),
            default=end,
        )
        cache_macro(latest_date, {"items": cache_items, "date": latest_date.isoformat()})
    update_job_state(MACRO_REFRESH_STATE_KEY, end)

    return total
