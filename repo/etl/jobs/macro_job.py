from __future__ import annotations

import os
from datetime import date

from etl.fetchers.akshare_macro_client import AKSHARE_MACRO_KEY_COUNT, fetch_all_akshare_macro_rows
from etl.fetchers.worldbank_client import get_indicator_series
from etl.loaders.pg_loader import count_latest_macro_rows, list_latest_macro_rows, upsert_macro
from etl.loaders.redis_cache import cache_macro
from etl.transformers.macro import normalize_macro_rows
from etl.utils.logging import get_logger
from etl.utils.state import get_job_state, update_job_state

LOGGER = get_logger(__name__)
MACRO_REFRESH_DAYS = max(1, int(os.getenv("MACRO_REFRESH_DAYS", "7")))
MACRO_REFRESH_STATE_KEY = "macro_remote_refresh"
WORLD_BANK_REFRESH_DAYS = max(7, int(os.getenv("WORLD_BANK_REFRESH_DAYS", "30")))
WORLD_BANK_REFRESH_STATE_KEY = "macro_world_bank_refresh"

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
EXPECTED_MACRO_KEY_COUNT = len(WORLD_BANK_INDICATORS) * len(WORLD_BANK_COUNTRIES) + AKSHARE_MACRO_KEY_COUNT
MACRO_MIN_KEY_COUNT = max(20, int(os.getenv("MACRO_MIN_KEY_COUNT", str(int(EXPECTED_MACRO_KEY_COUNT * 0.75)))))
AKSHARE_MIN_KEY_COUNT = max(8, int(os.getenv("AKSHARE_MIN_KEY_COUNT", str(max(8, int(AKSHARE_MACRO_KEY_COUNT * 0.5))))))


def macro_snapshot_is_healthy(min_key_count: int | None = None, *, include_world_bank: bool = False) -> bool:
    required = (
        MACRO_MIN_KEY_COUNT if include_world_bank else AKSHARE_MIN_KEY_COUNT
        if min_key_count is None
        else max(1, min_key_count)
    )
    current = count_latest_macro_rows(None if include_world_bank else "AK_%")
    if current < required:
        LOGGER.info(
            "macro snapshot incomplete: include_world_bank=%s latest_key_count=%s required=%s expected=%s",
            include_world_bank,
            current,
            required,
            EXPECTED_MACRO_KEY_COUNT if include_world_bank else AKSHARE_MACRO_KEY_COUNT,
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


def _should_refresh_world_bank(end: date, *, full_snapshot_healthy: bool) -> bool:
    remote_state = get_job_state(WORLD_BANK_REFRESH_STATE_KEY)
    if remote_state.last_success_date is None:
        return True
    age_days = (end - remote_state.last_success_date).days
    if age_days >= WORLD_BANK_REFRESH_DAYS:
        return True
    if not full_snapshot_healthy:
        LOGGER.info(
            "macro_job forcing world bank refresh because full snapshot coverage is incomplete; last_world_bank_refresh=%s",
            remote_state.last_success_date,
        )
        return True
    return False


def _refresh_world_bank_rows(start: date, end: date, *, log_prefix: str = "macro_job") -> int:
    total = 0
    series_count = 0
    wb_start = date(max(1960, start.year - 10), 1, 1)
    wb_end = date(end.year, 12, 31)

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
            series_count += 1

    if total <= 0:
        LOGGER.info("%s loaded world bank rows=0", log_prefix)
        return 0

    update_job_state(WORLD_BANK_REFRESH_STATE_KEY, end)
    LOGGER.info("%s loaded world bank rows=%s series=%s", log_prefix, total, series_count)
    return total


def run_macro_job(start: date, end: date) -> int:
    """Run macro job: refresh AkShare data and keep World Bank coverage in the same pass."""
    remote_state = get_job_state(MACRO_REFRESH_STATE_KEY)
    full_snapshot_healthy = macro_snapshot_is_healthy(include_world_bank=True)
    akshare_snapshot_healthy = macro_snapshot_is_healthy(include_world_bank=False)
    world_bank_refresh_due = _should_refresh_world_bank(end, full_snapshot_healthy=full_snapshot_healthy)

    akshare_refresh_due = True
    if remote_state.last_success_date is not None:
        age_days = (end - remote_state.last_success_date).days
        akshare_refresh_due = age_days >= MACRO_REFRESH_DAYS or not akshare_snapshot_healthy
        if not akshare_refresh_due and not world_bank_refresh_due and full_snapshot_healthy:
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
        if not akshare_refresh_due or not full_snapshot_healthy or world_bank_refresh_due:
            reasons: list[str] = []
            if not akshare_snapshot_healthy:
                reasons.append("akshare snapshot coverage is incomplete")
            if world_bank_refresh_due:
                reasons.append("world bank refresh is due")
            if not full_snapshot_healthy:
                reasons.append("full snapshot coverage is incomplete")
            LOGGER.info(
                "macro_job continuing refresh because %s; last_remote_refresh=%s",
                ", ".join(dict.fromkeys(reasons)) or "refresh is due",
                remote_state.last_success_date,
            )

    total = 0
    if akshare_refresh_due:
        akshare_rows = fetch_all_akshare_macro_rows(start=start, end=end)
        if akshare_rows:
            upsert_macro(akshare_rows)
            total += len(akshare_rows)
            akshare_key_count = len({str(row.get("key") or "") for row in akshare_rows if row.get("key")})
            update_job_state(MACRO_REFRESH_STATE_KEY, end)
            LOGGER.info("macro_job loaded akshare rows=%s keys=%s", len(akshare_rows), akshare_key_count)
        else:
            LOGGER.info("macro_job loaded akshare rows=0")
    else:
        LOGGER.info(
            "macro_job reused akshare snapshot; last_remote_refresh=%s refresh_days=%s",
            remote_state.last_success_date,
            MACRO_REFRESH_DAYS,
        )

    if world_bank_refresh_due:
        total += _refresh_world_bank_rows(start, end)
    else:
        world_bank_state = get_job_state(WORLD_BANK_REFRESH_STATE_KEY)
        LOGGER.info(
            "macro_job reused world bank snapshot; last_world_bank_refresh=%s refresh_days=%s",
            world_bank_state.last_success_date,
            WORLD_BANK_REFRESH_DAYS,
        )

    if total == 0:
        LOGGER.info("macro_job empty for %s to %s", start, end)
        return total

    _cache_latest_macro_rows()
    return total


def run_worldbank_macro_job(start: date, end: date) -> int:
    """Backward-compatible manual World Bank refresh entrypoint."""
    total = _refresh_world_bank_rows(start, end, log_prefix="worldbank_macro_job")
    if total <= 0:
        LOGGER.info("worldbank_macro_job empty for %s to %s", start, end)
        return 0
    _cache_latest_macro_rows()
    return total
