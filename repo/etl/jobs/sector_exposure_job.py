from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import os

from etl.fetchers.market_client import get_daily_prices, get_stock_basic, market_data_session
from etl.loaders.pg_loader import list_daily_price_rows, upsert_daily_prices, upsert_sector_exposure
from etl.loaders.redis_cache import cache_heatmap, cache_sector_exposure
from etl.transformers.heatmap import build_heatmap
from etl.transformers.sector_exposure import build_sector_exposure
from etl.utils.dates import date_range
from etl.utils.logging import get_logger
from etl.utils.normalize import validate_numeric_range

LOGGER = get_logger(__name__)


def _chunk_symbols(symbols: list[str], chunk_size: int) -> list[list[str]]:
    size = max(1, chunk_size)
    return [symbols[idx : idx + size] for idx in range(0, len(symbols), size)]


def _fetch_missing_daily_prices(symbols: list[str], as_of: date) -> list[dict]:
    if not symbols:
        return []
    batch_size = max(1, int(os.getenv("SECTOR_EXPOSURE_BATCH_SIZE", "200")))
    batch_workers = max(1, int(os.getenv("SECTOR_EXPOSURE_FETCH_WORKERS", "4")))
    batch_symbol_workers = max(1, int(os.getenv("SECTOR_EXPOSURE_BATCH_SYMBOL_WORKERS", "2")))
    batches = _chunk_symbols(symbols, batch_size)
    rows: list[dict] = []

    if batch_workers <= 1 or len(batches) == 1:
        for batch in batches:
            rows.extend(get_daily_prices(batch, as_of, workers=batch_symbol_workers))
        return rows

    LOGGER.info(
        "sector_exposure_job fetch workers=%s batch_size=%s batch_symbol_workers=%s batches=%s date=%s",
        batch_workers,
        batch_size,
        batch_symbol_workers,
        len(batches),
        as_of,
    )
    with ThreadPoolExecutor(max_workers=min(batch_workers, len(batches))) as executor:
        future_map = {
            executor.submit(get_daily_prices, batch, as_of, workers=batch_symbol_workers): idx
            for idx, batch in enumerate(batches, start=1)
        }
        for done, future in enumerate(as_completed(future_map), start=1):
            batch_no = future_map[future]
            try:
                rows.extend(future.result() or [])
            except Exception as exc:
                LOGGER.warning("sector_exposure_job batch failed %s/%s for %s: %s", batch_no, len(batches), as_of, exc)
            if done % 10 == 0 or done >= len(batches):
                LOGGER.info("sector_exposure_job fetch progress %s/%s for %s", done, len(batches), as_of)
    return rows


def run_sector_exposure_job(start: date, end: date) -> int:
    """Run sector exposure job."""
    total = 0
    LOGGER.info("sector_exposure_job loading stock basics")
    stock_rows = get_stock_basic()
    meta = {row.get("symbol"): row for row in stock_rows}
    symbols = [row.get("symbol") for row in stock_rows if row.get("symbol")]
    symbol_set = set(symbols)
    LOGGER.info("sector_exposure_job stock count=%s", len(symbols))
    with market_data_session():
        for as_of in date_range(start, end):
            stored_rows = [row for row in list_daily_price_rows(as_of) if row.get("symbol") in symbol_set]
            stored_symbols = {row.get("symbol") for row in stored_rows if row.get("symbol")}
            missing_symbols = [symbol for symbol in symbols if symbol not in stored_symbols]
            LOGGER.info(
                "sector_exposure_job local rows=%s missing=%s for %s",
                len(stored_rows),
                len(missing_symbols),
                as_of,
            )

            fetched_rows: list[dict] = []
            if missing_symbols:
                LOGGER.info("sector_exposure_job fetching missing daily prices for %s", as_of)
                fetched_rows = _fetch_missing_daily_prices(missing_symbols, as_of)
                LOGGER.info("sector_exposure_job fetched %s missing rows for %s", len(fetched_rows), as_of)
                if fetched_rows:
                    upsert_daily_prices(fetched_rows)

            daily_by_symbol = {
                row.get("symbol"): row
                for row in stored_rows + fetched_rows
                if row.get("symbol")
            }
            daily_rows = [daily_by_symbol[symbol] for symbol in symbols if symbol in daily_by_symbol]
            if not daily_rows:
                LOGGER.info("sector_exposure_job empty for %s", as_of)
                continue

            payload = []
            for row in daily_rows:
                symbol = row.get("symbol")
                info = meta.get(symbol) or {}
                payload.append(
                    {
                        "sector": info.get("sector") or "Unknown",
                        "market": info.get("market") or "ALL",
                        "close": row.get("close"),
                        "change": float(row.get("close") or 0) - float(row.get("open") or 0),
                    }
                )

            payload, _ = validate_numeric_range(payload, "close", min_value=0.0, context="sector_exposure")
            heatmap_rows = build_heatmap(payload)
            if heatmap_rows:
                cache_heatmap(as_of, {"date": as_of.isoformat(), "items": heatmap_rows})

            all_rows = build_sector_exposure(payload)
            LOGGER.info("sector_exposure_job built exposure rows=%s for %s", len(all_rows), as_of)

            db_rows = []
            if all_rows:
                db_rows.extend(
                    {"sector": item["sector"], "market": "ALL", "value": item["value"]}
                    for item in all_rows
                )
                cache_sector_exposure(as_of, {"date": as_of.isoformat(), "items": all_rows}, market=None)
                total += len(all_rows)

            for market in sorted({item.get("market") for item in payload if item.get("market")}):
                market_rows = build_sector_exposure(item for item in payload if item.get("market") == market)
                if not market_rows:
                    continue
                db_rows.extend(
                    {"sector": item["sector"], "market": market, "value": item["value"]}
                    for item in market_rows
                )
                cache_sector_exposure(as_of, {"date": as_of.isoformat(), "items": market_rows}, market=market)

            if db_rows:
                upsert_sector_exposure(db_rows)
                total += len(db_rows) - len(all_rows)
    return total
