from __future__ import annotations

from datetime import date

from etl.providers import get_provider

_provider = get_provider()
from etl.loaders.pg_loader import upsert_index_constituents, upsert_stocks
from etl.utils.dates import date_range
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)

INDEX_SYMBOLS = ["000016.SH", "000300.SH", "000688.SH", "899050.BJ", "HKHSI", "HKHSCEI", "HKHSTECH"]


def _market_from_symbol(symbol: str) -> str:
    upper = str(symbol or "").strip().upper()
    if upper.endswith(".HK"):
        return "HK"
    if upper.endswith((".SH", ".SZ", ".BJ")):
        return "A"
    if upper.endswith(".US"):
        return "US"
    return ""


def _stock_rows_from_constituents(rows: list[dict]) -> list[dict]:
    output: dict[str, dict] = {}
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        name = str(row.get("name") or "").strip()
        market = str(row.get("market") or "").strip().upper() or _market_from_symbol(symbol)
        sector = str(row.get("sector") or "").strip()
        if not name and not market and not sector:
            continue
        output[symbol] = {
            "symbol": symbol,
            "name": name or symbol,
            "market": market,
            "sector": sector or "Unknown",
        }
    return list(output.values())


def _normalize_constituent_weights(rows: list[dict]) -> list[dict]:
    by_index: dict[str, list[dict]] = {}
    for row in rows:
        index_symbol = str(row.get("index_symbol") or "").strip().upper()
        if not index_symbol:
            continue
        by_index.setdefault(index_symbol, []).append(row)

    for index_rows in by_index.values():
        weights = [float(row.get("weight") or 0.0) for row in index_rows if row.get("weight") is not None]
        if weights and sum(weights) > 1.5:
            for row in index_rows:
                if row.get("weight") is not None:
                    row["weight"] = float(row.get("weight") or 0.0) / 100.0
    return rows


def run_index_constituent_job(start: date, end: date) -> int:
    """Run index constituent job."""
    total = 0
    supported_hk_symbols = set(_provider.index.supported_hk_index_symbols())
    for as_of in date_range(start, end):
        batch = []
        for index_symbol in INDEX_SYMBOLS:
            canonical = _provider.market.normalize_index_symbol(index_symbol)
            if canonical in supported_hk_symbols:
                batch.extend(_provider.index.get_hk_index_constituents(canonical))
            else:
                batch.extend(_provider.index.get_index_constituents(canonical, as_of))
        if not batch:
            LOGGER.info("index_constituent_job empty for %s", as_of)
            continue
        batch = _normalize_constituent_weights(batch)
        stock_rows = _stock_rows_from_constituents(batch)
        if stock_rows:
            upsert_stocks(stock_rows)
        total += upsert_index_constituents(batch)
    return total
