from __future__ import annotations

from datetime import date

from etl.fetchers.baostock_client import baostock_session
from etl.fetchers.stock_basic_client import get_stock_basic
from etl.fetchers.tushare_client import get_daily_prices
from etl.loaders.pg_loader import upsert_sector_exposure
from etl.loaders.redis_cache import cache_sector_exposure
from etl.transformers.sector_exposure import build_sector_exposure
from etl.utils.dates import date_range
from etl.utils.logging import get_logger
from etl.utils.normalize import validate_numeric_range

LOGGER = get_logger(__name__)


def run_sector_exposure_job(start: date, end: date) -> int:
    """Run sector exposure job."""
    total = 0
    LOGGER.info("sector_exposure_job loading stock basics")
    stock_rows = get_stock_basic()
    meta = {row.get("symbol"): row for row in stock_rows}
    symbols = [row.get("symbol") for row in stock_rows if row.get("symbol")]
    LOGGER.info("sector_exposure_job stock count=%s", len(symbols))
    with baostock_session():
        for as_of in date_range(start, end):
            LOGGER.info("sector_exposure_job fetching daily prices for %s", as_of)
            daily_rows = get_daily_prices(symbols, as_of)
            LOGGER.info("sector_exposure_job fetched %s rows for %s", len(daily_rows), as_of)
            if not daily_rows:
                LOGGER.info("sector_exposure_job empty for %s", as_of)
                continue
            payload = []
            for row in daily_rows:
                symbol = row.get("symbol")
                info = meta.get(symbol) or {}
                payload.append({
                    "sector": info.get("sector") or "未知",
                    "market": info.get("market") or "ALL",
                    "close": row.get("close"),
                })
            payload, _ = validate_numeric_range(payload, "close", min_value=0.0, context="sector_exposure")
            exposure_rows = build_sector_exposure(payload)
            LOGGER.info("sector_exposure_job built exposure rows=%s for %s", len(exposure_rows), as_of)
            if exposure_rows:
                upsert_sector_exposure(
                    [
                        {"sector": item["sector"], "market": "ALL", "value": item["value"]}
                        for item in exposure_rows
                    ]
                )
                cache_sector_exposure(as_of, {"date": as_of.isoformat(), "items": exposure_rows})
                total += len(exposure_rows)
    return total
