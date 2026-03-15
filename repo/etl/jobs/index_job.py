from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
import os

from etl.fetchers.market_client import get_daily_prices, get_index_daily, get_stock_basic
from etl.loaders.pg_loader import list_daily_price_rows, upsert_daily_prices, upsert_indices, upsert_stocks
from etl.loaders.redis_cache import cache_risk
from etl.transformers.heatmap import normalize_daily_rows
from etl.transformers.indicators import calc_max_drawdown, calc_volatility
from etl.utils.dates import date_range
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


def _chunk_symbols(symbols: list[str], chunk_size: int) -> list[list[str]]:
    size = max(1, chunk_size)
    return [symbols[idx : idx + size] for idx in range(0, len(symbols), size)]


def _fetch_missing_index_daily_prices(symbols: list[str], as_of: date) -> list[dict]:
    if not symbols:
        return []
    batch_size = max(1, int(os.getenv("INDEX_JOB_BATCH_SIZE", "20")))
    batch_workers = max(1, int(os.getenv("INDEX_JOB_FETCH_WORKERS", "2")))
    batch_symbol_workers = max(1, int(os.getenv("INDEX_JOB_BATCH_SYMBOL_WORKERS", "2")))
    batches = _chunk_symbols(symbols, batch_size)
    rows: list[dict] = []

    if batch_workers <= 1 or len(batches) == 1:
        for batch in batches:
            rows.extend(get_daily_prices(batch, as_of, workers=batch_symbol_workers))
        return rows

    LOGGER.info(
        "index_job fetch workers=%s batch_size=%s batch_symbol_workers=%s batches=%s date=%s",
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
                LOGGER.warning("index_job batch failed %s/%s for %s: %s", batch_no, len(batches), as_of, exc)
            if done % 10 == 0 or done >= len(batches):
                LOGGER.info("index_job fetch progress %s/%s for %s", done, len(batches), as_of)
    return rows


def _load_index_daily_rows(symbols: list[str], as_of: date) -> list[dict]:
    symbol_set = set(symbols)
    stored_rows = [row for row in list_daily_price_rows(as_of) if row.get("symbol") in symbol_set]
    stored_symbols = {row.get("symbol") for row in stored_rows if row.get("symbol")}
    missing_symbols = [symbol for symbol in symbols if symbol not in stored_symbols]
    LOGGER.info("index_job local rows=%s missing=%s for %s", len(stored_rows), len(missing_symbols), as_of)

    fetched_rows: list[dict] = []
    if missing_symbols:
        LOGGER.info("index_job fetching missing daily prices for %s", as_of)
        fetched_rows = _fetch_missing_index_daily_prices(missing_symbols, as_of)
        LOGGER.info("index_job fetched %s missing rows for %s", len(fetched_rows), as_of)
        if fetched_rows:
            upsert_daily_prices(fetched_rows)

    daily_by_symbol = {
        row.get("symbol"): row
        for row in stored_rows + fetched_rows
        if row.get("symbol")
    }
    ordered_rows = [daily_by_symbol[symbol] for symbol in symbols if symbol in daily_by_symbol]
    return normalize_daily_rows(ordered_rows)


def run_index_job(start: date, end: date) -> int:
    """Run index job: fetch indices and store into DB (incremental)."""
    stock_rows = get_stock_basic()
    upsert_stocks(stock_rows)
    price_history: dict[str, list[float]] = {}

    total = 0
    for as_of in date_range(start, end):
        index_rows = get_index_daily(as_of)
        if not index_rows:
            LOGGER.info("index_job empty for %s", as_of)
            continue
        upsert_indices(index_rows)

        symbols = [row["symbol"] for row in index_rows]
        daily_rows = _load_index_daily_rows(symbols, as_of)
        if daily_rows:
            LOGGER.info("index_job ready daily rows=%s for %s", len(daily_rows), as_of)
        total += len(daily_rows)

        closes = [row["close"] for row in daily_rows]
        returns = []
        for idx in range(1, len(closes)):
            if closes[idx - 1] == 0:
                continue
            returns.append((closes[idx] - closes[idx - 1]) / closes[idx - 1])
        cache_risk(
            "ALL",
            {
                "max_drawdown": calc_max_drawdown(closes),
                "volatility": calc_volatility(returns),
                "as_of": as_of,
            },
        )

        for row in daily_rows:
            symbol = row.get("symbol")
            if not symbol:
                continue
            series = price_history.setdefault(symbol, [])
            series.append(float(row.get("close", 0) or 0))
            price_history[symbol] = series[-60:]
            symbol_returns = [
                (series[idx] - series[idx - 1]) / series[idx - 1]
                for idx in range(1, len(series))
                if series[idx - 1]
            ]
            cache_risk(
                symbol,
                {
                    "symbol": symbol,
                    "max_drawdown": calc_max_drawdown(price_history[symbol]),
                    "volatility": calc_volatility(symbol_returns),
                    "as_of": as_of,
                },
            )

    return total
