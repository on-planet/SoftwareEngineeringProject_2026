from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import os

from etl.fetchers.market_client import get_daily_prices, get_stock_basic, market_data_session
from etl.fetchers.snowball_client import get_stock_quote_detail
from etl.loaders.pg_loader import (
    list_daily_price_rows,
    list_stock_valuation_rows,
    upsert_daily_prices,
    upsert_sector_exposure,
    upsert_sector_exposure_summary,
    upsert_stock_valuation_snapshots,
)
from etl.loaders.redis_cache import cache_heatmap, cache_sector_exposure
from etl.transformers.heatmap import build_heatmap
from etl.transformers.sector_exposure import build_sector_exposure
from etl.utils.dates import date_range
from etl.utils.logging import get_logger
from etl.utils.normalize import validate_numeric_range
from etl.utils.sector_taxonomy import normalize_sector_name

LOGGER = get_logger(__name__)
SECTOR_EXPOSURE_BASIS = "market_value"


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


def _should_fetch_live_valuations(as_of: date) -> bool:
    lag_days = max(0, int(os.getenv("SECTOR_EXPOSURE_VALUATION_LAG_DAYS", "2")))
    delta = (date.today() - as_of).days
    return 0 <= delta <= lag_days


def _valuation_value(snapshot: dict | None) -> float | None:
    if not isinstance(snapshot, dict):
        return None
    for key in ("float_market_cap", "market_cap"):
        value = snapshot.get(key)
        try:
            numeric = float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            numeric = 0.0
        if numeric > 0:
            return numeric
    return None


def _fallback_exposure_value(meta: dict | None, daily_row: dict | None) -> float | None:
    meta = meta or {}
    daily_row = daily_row or {}
    market = str(meta.get("market") or "").strip().upper()
    if market != "HK":
        return None
    for key in ("float_market_cap", "market_cap", "total_market_cap", "market_value"):
        value = meta.get(key)
        try:
            numeric = float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            numeric = 0.0
        if numeric > 0:
            return numeric
    close = daily_row.get("close")
    try:
        numeric_close = float(close) if close is not None else 0.0
    except (TypeError, ValueError):
        numeric_close = 0.0
    if numeric_close > 0:
        # Fallback proxy for HK when market cap snapshots are unavailable.
        return numeric_close
    return None


def _fetch_missing_valuation_snapshots(symbols: list[str], as_of: date) -> list[dict]:
    if not symbols or not _should_fetch_live_valuations(as_of):
        return []
    workers = max(1, int(os.getenv("SECTOR_EXPOSURE_VALUATION_WORKERS", "8")))
    LOGGER.info("sector_exposure_job fetching live valuation snapshots workers=%s count=%s date=%s", workers, len(symbols), as_of)

    def _fetch(symbol: str) -> dict | None:
        detail = get_stock_quote_detail(symbol)
        if not detail:
            return None
        market_cap = detail.get("market_cap")
        float_market_cap = detail.get("float_market_cap")
        if market_cap in (None, 0) and float_market_cap in (None, 0):
            return None
        return {
            "symbol": symbol,
            "date": as_of,
            "market_cap": market_cap,
            "float_market_cap": float_market_cap,
            "source": "snowball_quote_detail",
        }

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=min(workers, len(symbols))) as executor:
        future_map = {executor.submit(_fetch, symbol): symbol for symbol in symbols}
        for done, future in enumerate(as_completed(future_map), start=1):
            try:
                row = future.result()
            except Exception as exc:
                LOGGER.warning("sector_exposure_job valuation fetch failed for %s on %s: %s", future_map[future], as_of, exc)
                row = None
            if row:
                rows.append(row)
            if done % 200 == 0 or done >= len(future_map):
                LOGGER.info("sector_exposure_job valuation progress %s/%s for %s", done, len(future_map), as_of)
    return rows


def run_stock_valuation_backfill(start: date, end: date) -> int:
    total = 0
    LOGGER.info("stock_valuation_backfill loading stock basics")
    stock_rows = get_stock_basic(force_refresh=False)
    symbols = [row.get("symbol") for row in stock_rows if row.get("symbol")]
    symbol_set = set(symbols)
    with market_data_session():
        for as_of in date_range(start, end):
            if not _should_fetch_live_valuations(as_of):
                LOGGER.info("stock_valuation_backfill skip stale date %s", as_of)
                continue
            daily_rows = [row for row in list_daily_price_rows(as_of) if row.get("symbol") in symbol_set]
            if not daily_rows:
                LOGGER.info("stock_valuation_backfill empty daily rows for %s", as_of)
                continue
            existing = {row.get("symbol") for row in list_stock_valuation_rows(as_of) if row.get("symbol")}
            missing = [row.get("symbol") for row in daily_rows if row.get("symbol") and row.get("symbol") not in existing]
            if not missing:
                LOGGER.info("stock_valuation_backfill no missing valuations for %s", as_of)
                continue
            fetched = _fetch_missing_valuation_snapshots(missing, as_of)
            if not fetched:
                LOGGER.info("stock_valuation_backfill fetched 0 rows for %s", as_of)
                continue
            total += upsert_stock_valuation_snapshots(fetched)
            LOGGER.info("stock_valuation_backfill wrote %s rows for %s", len(fetched), as_of)
    return total


def run_sector_exposure_job(start: date, end: date) -> int:
    """Run sector exposure job."""
    total = 0
    LOGGER.info("sector_exposure_job loading stock basics")
    stock_rows = get_stock_basic(force_refresh=True)
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

            valuation_by_symbol = {
                row.get("symbol"): row
                for row in list_stock_valuation_rows(as_of)
                if row.get("symbol")
            }
            missing_valuation_symbols = [
                row.get("symbol")
                for row in daily_rows
                if row.get("symbol") and row.get("symbol") not in valuation_by_symbol
            ]
            fetched_valuation_rows = _fetch_missing_valuation_snapshots(missing_valuation_symbols, as_of)
            if fetched_valuation_rows:
                upsert_stock_valuation_snapshots(fetched_valuation_rows)
                valuation_by_symbol.update({row["symbol"]: row for row in fetched_valuation_rows if row.get("symbol")})

            payload = []
            exposure_payload = []
            for row in daily_rows:
                symbol = row.get("symbol")
                info = meta.get(symbol) or {}
                normalized_sector = normalize_sector_name(info.get("sector"), market=info.get("market"))
                payload.append(
                    {
                        "sector": normalized_sector,
                        "market": info.get("market") or "ALL",
                        "close": row.get("close"),
                        "change": float(row.get("close") or 0) - float(row.get("open") or 0),
                    }
                )
                valuation = valuation_by_symbol.get(symbol)
                exposure_payload.append(
                    {
                        "sector": normalized_sector,
                        "market": info.get("market") or "ALL",
                        "value": _valuation_value(valuation) or _fallback_exposure_value(info, row),
                    }
                )

            payload, _ = validate_numeric_range(payload, "close", min_value=0.0, context="sector_exposure")
            heatmap_rows = build_heatmap(payload)
            if heatmap_rows:
                cache_heatmap(as_of, {"date": as_of.isoformat(), "items": heatmap_rows})

            all_payload = build_sector_exposure(exposure_payload, basis=SECTOR_EXPOSURE_BASIS)
            all_rows = all_payload["items"]
            LOGGER.info(
                "sector_exposure_job built exposure rows=%s coverage=%.4f for %s",
                len(all_rows),
                float(all_payload.get("coverage") or 0.0),
                as_of,
            )

            db_rows = []
            summary_rows = []
            if all_rows:
                db_rows.extend(
                    {
                        "date": as_of,
                        "sector": item["sector"],
                        "market": "ALL",
                        "basis": SECTOR_EXPOSURE_BASIS,
                        "value": item["value"],
                        "weight": item["weight"],
                        "symbol_count": item["symbol_count"],
                    }
                    for item in all_rows
                )
                summary_rows.append(
                    {
                        "date": as_of,
                        "market": "ALL",
                        "basis": SECTOR_EXPOSURE_BASIS,
                        "total_value": all_payload["total_value"],
                        "total_symbol_count": all_payload["total_symbol_count"],
                        "covered_symbol_count": all_payload["covered_symbol_count"],
                        "classified_symbol_count": all_payload["classified_symbol_count"],
                        "unknown_symbol_count": all_payload["unknown_symbol_count"],
                        "unknown_value": all_payload["unknown_value"],
                        "coverage": all_payload["coverage"],
                    }
                )
                cache_sector_exposure(
                    as_of,
                    {
                        "date": as_of.isoformat(),
                        "basis": SECTOR_EXPOSURE_BASIS,
                        "coverage": all_payload["coverage"],
                        "unknown_weight": (
                            (all_payload["unknown_value"] / all_payload["total_value"]) if all_payload["total_value"] else 0.0
                        ),
                        "total_value": all_payload["total_value"],
                        "items": all_rows,
                    },
                    market=None,
                    basis=SECTOR_EXPOSURE_BASIS,
                )
                total += len(all_rows)

            for market in sorted({item.get("market") for item in exposure_payload if item.get("market")}):
                market_payload = build_sector_exposure(
                    (item for item in exposure_payload if item.get("market") == market),
                    basis=SECTOR_EXPOSURE_BASIS,
                )
                market_rows = market_payload["items"]
                if not market_rows:
                    continue
                db_rows.extend(
                    {
                        "date": as_of,
                        "sector": item["sector"],
                        "market": market,
                        "basis": SECTOR_EXPOSURE_BASIS,
                        "value": item["value"],
                        "weight": item["weight"],
                        "symbol_count": item["symbol_count"],
                    }
                    for item in market_rows
                )
                summary_rows.append(
                    {
                        "date": as_of,
                        "market": market,
                        "basis": SECTOR_EXPOSURE_BASIS,
                        "total_value": market_payload["total_value"],
                        "total_symbol_count": market_payload["total_symbol_count"],
                        "covered_symbol_count": market_payload["covered_symbol_count"],
                        "classified_symbol_count": market_payload["classified_symbol_count"],
                        "unknown_symbol_count": market_payload["unknown_symbol_count"],
                        "unknown_value": market_payload["unknown_value"],
                        "coverage": market_payload["coverage"],
                    }
                )
                cache_sector_exposure(
                    as_of,
                    {
                        "date": as_of.isoformat(),
                        "basis": SECTOR_EXPOSURE_BASIS,
                        "coverage": market_payload["coverage"],
                        "unknown_weight": (
                            (market_payload["unknown_value"] / market_payload["total_value"])
                            if market_payload["total_value"]
                            else 0.0
                        ),
                        "total_value": market_payload["total_value"],
                        "items": market_rows,
                    },
                    market=market,
                    basis=SECTOR_EXPOSURE_BASIS,
                )

            if db_rows:
                upsert_sector_exposure(db_rows)
            if summary_rows:
                upsert_sector_exposure_summary(summary_rows)
            if db_rows:
                total += len(db_rows) - len(all_rows)
    return total
