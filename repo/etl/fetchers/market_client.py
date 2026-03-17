from __future__ import annotations

from contextlib import contextmanager
from datetime import date
import json
import os
from pathlib import Path
import time
from typing import List

from etl.loaders.pg_loader import list_stock_rows, upsert_stocks
from etl.fetchers.akshare_hk_stock_client import fetch_hk_stock_universe_rows
from etl.fetchers.baostock_client import get_stock_industry
from etl.fetchers.snowball_client import (
    get_daily_prices as sb_get_daily_prices,
    get_financials as sb_get_financials,
    get_index_daily as sb_get_index_daily,
    get_monthly_prices as sb_get_monthly_prices,
    get_stock_basics as sb_get_stock_basics,
    snowball_session,
)
from etl.utils.baostock_industry_cache import (
    load_baostock_industry_cache,
    save_baostock_industry_cache,
)
from etl.utils.stock_basics_cache import load_stock_basics_cache, save_stock_basics_cache
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)
STATE_DIR = Path(__file__).resolve().parents[1] / "state"
HK_UNIVERSE_CHECKPOINT_PATH = STATE_DIR / "hk_stock_universe_sync_checkpoint.json"
HK_UNIVERSE_MIN_COUNT = max(100, int(os.getenv("HK_UNIVERSE_MIN_COUNT", "1500")))
HK_UNIVERSE_REFRESH_COOLDOWN_SECONDS = max(
    300, int(os.getenv("HK_UNIVERSE_REFRESH_COOLDOWN_SECONDS", "1800"))
)
HK_UNIVERSE_SYNC_BATCH_SIZE = max(1, int(os.getenv("HK_UNIVERSE_SYNC_BATCH_SIZE", "200")))
_HK_UNIVERSE_LAST_ATTEMPT_AT = 0.0


@contextmanager
def market_data_session():
    with snowball_session():
        yield


def _can_apply_baostock_sector(symbol: str) -> bool:
    normalized = str(symbol or "").strip().upper()
    return normalized.endswith((".SH", ".SZ", ".BJ"))


def _should_replace_name(current_name: str | None, symbol: str) -> bool:
    text = str(current_name or "").strip()
    if not text:
        return True
    if text.upper() == str(symbol or "").strip().upper():
        return True
    return not any("\u4e00" <= char <= "\u9fff" for char in text)


def _needs_baostock_sector(value: str | None) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    return text in {"Unknown", "未知", "未分类"}


def _needs_baostock_enrichment(row: dict) -> bool:
    symbol = str(row.get("symbol") or "").strip()
    if not symbol or not _can_apply_baostock_sector(symbol):
        return False
    return _should_replace_name(str(row.get("name") or ""), symbol) or _needs_baostock_sector(row.get("sector"))


def _merge_baostock_rows(rows: List[dict], baostock_rows: List[dict]) -> List[dict]:
    if not rows or not baostock_rows:
        return rows
    by_symbol = {str(row.get("symbol") or "").strip(): row for row in baostock_rows if row.get("symbol")}
    for row in rows:
        symbol = str(row.get("symbol") or "").strip()
        if not symbol or not _can_apply_baostock_sector(symbol):
            continue
        baostock_row = by_symbol.get(symbol)
        if not baostock_row:
            continue
        sector = str(baostock_row.get("sector") or "").strip()
        if sector:
            row["sector"] = sector
        baostock_name = str(baostock_row.get("name") or "").strip()
        if baostock_name and _should_replace_name(str(row.get("name") or ""), symbol):
            row["name"] = baostock_name
    return rows


def _enrich_with_cached_baostock(rows: List[dict], requested: list[str] | None = None) -> List[dict]:
    if not rows:
        return rows
    baostock_rows = load_baostock_industry_cache(requested, allow_stale=True)
    if not baostock_rows:
        return rows
    return _merge_baostock_rows(rows, baostock_rows)


def _count_market_rows(rows: list[dict], market: str) -> int:
    target = str(market or "").strip().upper()
    return sum(1 for row in rows if str(row.get("market") or "").strip().upper() == target)


def _requested_hk_symbols(requested: list[str] | None) -> set[str]:
    return {
        str(symbol).strip().upper()
        for symbol in requested or []
        if str(symbol).strip().upper().endswith(".HK")
    }


def _has_requested_hk_symbols(rows: list[dict], requested: list[str] | None) -> bool:
    hk_symbols = _requested_hk_symbols(requested)
    if not hk_symbols:
        return True
    present = {str(row.get("symbol") or "").strip().upper() for row in rows if row.get("symbol")}
    return hk_symbols.issubset(present)


def _needs_hk_universe_sync(rows: list[dict], requested: list[str] | None) -> bool:
    if requested is not None:
        return not _has_requested_hk_symbols(rows, requested)
    return _count_market_rows(rows, "HK") < HK_UNIVERSE_MIN_COUNT


def _load_hk_universe_checkpoint() -> dict | None:
    if not HK_UNIVERSE_CHECKPOINT_PATH.exists():
        return None
    try:
        payload = json.loads(HK_UNIVERSE_CHECKPOINT_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.warning("hk stock universe checkpoint load failed [%s]: %s", HK_UNIVERSE_CHECKPOINT_PATH, exc)
        return None
    return payload if isinstance(payload, dict) else None


def _save_hk_universe_checkpoint(rows: list[dict], next_index: int) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "rows": rows,
        "next_index": max(0, next_index),
        "updated_at": time.time(),
    }
    HK_UNIVERSE_CHECKPOINT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _clear_hk_universe_checkpoint() -> None:
    if not HK_UNIVERSE_CHECKPOINT_PATH.exists():
        return
    try:
        HK_UNIVERSE_CHECKPOINT_PATH.unlink()
    except OSError:
        return


def sync_hk_stock_universe(*, force: bool = False) -> int:
    global _HK_UNIVERSE_LAST_ATTEMPT_AT
    checkpoint = _load_hk_universe_checkpoint()
    rows = [row for row in (checkpoint or {}).get("rows") or [] if isinstance(row, dict) and row.get("symbol")]
    try:
        start_index = max(0, int((checkpoint or {}).get("next_index") or 0))
    except Exception:
        start_index = 0
    if not rows:
        now = time.monotonic()
        if not force and now - _HK_UNIVERSE_LAST_ATTEMPT_AT < HK_UNIVERSE_REFRESH_COOLDOWN_SECONDS:
            return 0
        _HK_UNIVERSE_LAST_ATTEMPT_AT = now
        rows = fetch_hk_stock_universe_rows()
        start_index = 0
        if rows:
            _save_hk_universe_checkpoint(rows, 0)
    else:
        LOGGER.info("hk stock universe resume rows=%s next_index=%s", len(rows), start_index)
    if not rows:
        return 0
    start_index = min(start_index, len(rows))
    for batch_start in range(start_index, len(rows), HK_UNIVERSE_SYNC_BATCH_SIZE):
        batch = rows[batch_start : batch_start + HK_UNIVERSE_SYNC_BATCH_SIZE]
        batch_end = batch_start + len(batch)
        upsert_stocks(batch)
        save_stock_basics_cache(batch, merge=True)
        _save_hk_universe_checkpoint(rows, batch_end)
        LOGGER.info("hk stock universe sync progress %s/%s", batch_end, len(rows))
    _clear_hk_universe_checkpoint()
    LOGGER.info("hk stock universe synced rows=%s", len(rows))
    return len(rows)


def _maybe_sync_hk_universe(rows: list[dict], requested: list[str] | None, *, force: bool = False) -> list[dict]:
    if not _needs_hk_universe_sync(rows, requested):
        return rows
    synced = sync_hk_stock_universe(force=force)
    if synced <= 0:
        return rows
    refreshed_rows = load_stock_basics_cache(requested, allow_stale=True)
    return refreshed_rows or rows


def warm_stock_basic_enrichment(symbols: list[str] | None = None) -> int:
    requested = [str(symbol).strip() for symbol in symbols or [] if str(symbol).strip()] or None
    stock_rows = load_stock_basics_cache(requested, allow_stale=True)
    if not stock_rows and requested is None:
        db_rows = list_stock_rows()
        if db_rows:
            save_stock_basics_cache(db_rows)
            stock_rows = load_stock_basics_cache(requested, allow_stale=True)
    pending_symbols = [
        str(row.get("symbol") or "").strip()
        for row in stock_rows
        if _needs_baostock_enrichment(row)
    ]
    if not pending_symbols:
        return 0
    cached_baostock = load_baostock_industry_cache(pending_symbols, allow_stale=True)
    covered = {str(row.get("symbol") or "").strip() for row in cached_baostock if row.get("symbol")}
    missing_symbols = [symbol for symbol in pending_symbols if symbol not in covered]
    if not missing_symbols:
        save_stock_basics_cache(_enrich_with_cached_baostock(stock_rows, requested), merge=True)
        return len(cached_baostock)
    fresh_rows = get_stock_industry(as_of=date.today())
    if not fresh_rows:
        return len(cached_baostock)
    save_baostock_industry_cache(fresh_rows, merge=True)
    save_stock_basics_cache(_enrich_with_cached_baostock(stock_rows, requested), merge=True)
    return len(fresh_rows)


def get_stock_basic(
    symbols: list[str] | None = None,
    *,
    force_refresh: bool = False,
    allow_stale_cache: bool = True,
) -> List[dict]:
    requested = [str(symbol).strip() for symbol in symbols or [] if str(symbol).strip()] or None
    requested_count = len(set(requested or []))

    if not force_refresh:
        cached_rows = load_stock_basics_cache(requested, allow_stale=allow_stale_cache)
        cached_rows = _maybe_sync_hk_universe(cached_rows, requested, force=False)
        if cached_rows and (requested is None or len(cached_rows) >= requested_count):
            cached_rows = _enrich_with_cached_baostock(cached_rows, requested)
            save_stock_basics_cache(cached_rows, merge=bool(requested))
            return cached_rows

        db_rows = list_stock_rows()
        if db_rows:
            save_stock_basics_cache(db_rows)
            normalized_db_rows = load_stock_basics_cache(requested, allow_stale=True)
            normalized_db_rows = _maybe_sync_hk_universe(normalized_db_rows, requested, force=False)
            normalized_db_rows = _enrich_with_cached_baostock(normalized_db_rows, requested)
            if normalized_db_rows:
                save_stock_basics_cache(normalized_db_rows, merge=bool(requested))
            if requested:
                if len(normalized_db_rows) >= requested_count:
                    return normalized_db_rows
            else:
                return normalized_db_rows or db_rows

    rows = sb_get_stock_basics(requested)
    rows = _maybe_sync_hk_universe(rows, requested, force=force_refresh or requested is None)
    if rows:
        baostock_rows = load_baostock_industry_cache(requested, allow_stale=True)
        rows = _merge_baostock_rows(rows, baostock_rows)
        cached_baostock_symbols = {str(item.get("symbol") or "").strip() for item in baostock_rows if item.get("symbol")}
        missing_symbols = [
            str(row.get("symbol") or "").strip()
            for row in rows
            if _needs_baostock_enrichment(row)
            and str(row.get("symbol") or "").strip() not in cached_baostock_symbols
        ]
        if missing_symbols:
            fresh_rows = get_stock_industry(as_of=date.today())
            if fresh_rows:
                save_baostock_industry_cache(fresh_rows, merge=True)
                rows = _merge_baostock_rows(rows, fresh_rows)
        save_stock_basics_cache(rows, merge=bool(requested))
    return rows


def get_index_daily(as_of: date) -> List[dict]:
    return sb_get_index_daily(as_of)


def get_daily_prices(symbols, as_of: date, *, workers: int | None = None) -> List[dict]:
    return sb_get_daily_prices(symbols, as_of, workers=workers)


def get_monthly_prices(symbols, as_of: date) -> List[dict]:
    return sb_get_monthly_prices(symbols, as_of)


def get_financials(symbol: str, period: str) -> dict:
    return sb_get_financials(symbol, period)
