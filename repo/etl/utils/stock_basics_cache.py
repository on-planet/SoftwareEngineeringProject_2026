from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

from etl.fetchers.snowball_client import normalize_symbol
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)
STATE_DIR = Path(__file__).resolve().parents[1] / "state"
CACHE_PATH = STATE_DIR / "stock_basics_cache.json"
DEFAULT_MAX_AGE_HOURS = int(os.getenv("STOCK_BASICS_CACHE_MAX_AGE_HOURS", "24"))


def _ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _load_payload() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception as exc:
        LOGGER.warning("stock basics cache load failed [%s]: %s", CACHE_PATH, exc)
        return {}


def _normalized_row_payload(row: dict, symbol: str) -> dict:
    return {
        "symbol": symbol,
        "name": str(row.get("name") or symbol),
        "market": str(row.get("market") or ""),
        "sector": str(row.get("sector") or "Unknown"),
    }


def _row_score(row: dict) -> int:
    score = 0
    symbol = str(row.get("symbol") or "")
    name = str(row.get("name") or "")
    market = str(row.get("market") or "")
    sector = str(row.get("sector") or "")
    if name and name != symbol:
        score += 2
    if market:
        score += 1
    if sector and sector != "Unknown":
        score += 1
    return score


def _normalize_rows(rows: Iterable[dict], symbols: set[str] | None = None) -> list[dict]:
    by_symbol: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_symbol = str(row.get("symbol") or "").strip()
        symbol = normalize_symbol(raw_symbol)
        if not symbol:
            continue
        if symbols is not None and symbol not in symbols:
            continue
        candidate = _normalized_row_payload(row, symbol)
        current = by_symbol.get(symbol)
        if current is None or _row_score(candidate) >= _row_score(current):
            by_symbol[symbol] = candidate
    output = list(by_symbol.values())
    output.sort(key=lambda item: item["symbol"])
    return output


def _updated_at(payload: dict) -> datetime | None:
    value = str(payload.get("updated_at") or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def load_stock_basics_cache(
    symbols: Iterable[str] | None = None,
    *,
    allow_stale: bool = True,
    max_age_hours: int | None = None,
) -> list[dict]:
    payload = _load_payload()
    rows = payload.get("items")
    if not isinstance(rows, list) or not rows:
        return []
    max_age = DEFAULT_MAX_AGE_HOURS if max_age_hours is None else max_age_hours
    updated_at = _updated_at(payload)
    if not allow_stale and updated_at is not None and max_age >= 0:
        if updated_at < datetime.now() - timedelta(hours=max_age):
            return []
    symbol_filter = {normalize_symbol(str(symbol).strip()) for symbol in symbols or [] if str(symbol).strip()} or None
    return _normalize_rows(rows, symbol_filter)


def save_stock_basics_cache(rows: Iterable[dict], *, merge: bool = False) -> int:
    normalized = _normalize_rows(rows)
    if not normalized:
        return 0

    by_symbol: dict[str, dict] = {}
    if merge:
        for row in load_stock_basics_cache():
            by_symbol[row["symbol"]] = row
    for row in normalized:
        by_symbol[row["symbol"]] = row

    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "items": sorted(by_symbol.values(), key=lambda item: item["symbol"]),
    }
    _ensure_state_dir()
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(payload["items"])
