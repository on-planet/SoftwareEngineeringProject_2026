from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

from etl.fetchers.snowball_client import normalize_symbol
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)
STATE_DIR = Path(__file__).resolve().parents[1] / "state"
CACHE_PATH = STATE_DIR / "baostock_industry_cache.json"
DEFAULT_MAX_AGE_HOURS = int(os.getenv("BAOSTOCK_INDUSTRY_CACHE_MAX_AGE_HOURS", "168"))


def _ensure_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def _load_payload() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        raw = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except Exception as exc:
        LOGGER.warning("baostock industry cache load failed [%s]: %s", CACHE_PATH, exc)
        return {}


def _parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except Exception:
            continue
    return None


def _updated_at(payload: dict) -> datetime | None:
    value = str(payload.get("updated_at") or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _normalized_row_payload(row: dict, symbol: str) -> dict:
    update_date = _parse_date(row.get("update_date")) or None
    return {
        "symbol": symbol,
        "name": str(row.get("name") or "").strip() or None,
        "sector": str(row.get("sector") or "").strip() or None,
        "industry_classification": str(row.get("industry_classification") or "").strip() or None,
        "update_date": update_date,
    }


def _row_score(row: dict) -> int:
    score = 0
    if str(row.get("name") or "").strip():
        score += 2
    if str(row.get("sector") or "").strip():
        score += 2
    if str(row.get("industry_classification") or "").strip():
        score += 1
    if row.get("update_date"):
        score += 1
    return score


def _normalize_rows(rows: Iterable[dict], symbols: set[str] | None = None) -> list[dict]:
    by_symbol: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = normalize_symbol(str(row.get("symbol") or "").strip())
        if not symbol:
            continue
        if symbols is not None and symbol not in symbols:
            continue
        candidate = _normalized_row_payload(row, symbol)
        current = by_symbol.get(symbol)
        if current is None or _row_score(candidate) >= _row_score(current):
            by_symbol[symbol] = candidate
    return [by_symbol[key] for key in sorted(by_symbol)]


def load_baostock_industry_cache(
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


def save_baostock_industry_cache(rows: Iterable[dict], *, merge: bool = False) -> int:
    normalized = _normalize_rows(rows)
    if not normalized:
        return 0
    by_symbol: dict[str, dict] = {}
    if merge:
        for row in load_baostock_industry_cache():
            by_symbol[row["symbol"]] = row
    for row in normalized:
        by_symbol[row["symbol"]] = row
    payload = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "items": [
            {
                **by_symbol[key],
                "update_date": by_symbol[key]["update_date"].isoformat()
                if isinstance(by_symbol[key].get("update_date"), date)
                else by_symbol[key].get("update_date"),
            }
            for key in sorted(by_symbol)
        ],
    }
    _ensure_state_dir()
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(payload["items"])
