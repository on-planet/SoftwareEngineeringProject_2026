from __future__ import annotations

from datetime import date

from etl.fetchers.worldbank_client import get_indicator_series
from etl.loaders.pg_loader import upsert_macro
from etl.loaders.redis_cache import cache_macro
from etl.transformers.macro import normalize_macro_rows
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)

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


def run_macro_job(start: date, end: date) -> int:
    """Run macro job: fetch World Bank indicators and store into DB."""
    total = 0
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

    if total == 0:
        LOGGER.info("macro_job empty for %s to %s", start, end)
        return total

    latest_date = end
    cache_items = []
    for name, indicator in WORLD_BANK_INDICATORS.items():
        for country in WORLD_BANK_COUNTRIES:
            fetched = get_indicator_series(country, indicator, wb_start, wb_end)
            if not fetched:
                continue
            for row in fetched:
                row["key"] = f"{name}:{country}"
            rows = normalize_macro_rows(fetched)
            if rows:
                cache_items.extend(rows[-1:])

    if cache_items:
        cache_macro(latest_date, {"items": cache_items, "date": latest_date.isoformat()})

    return total
