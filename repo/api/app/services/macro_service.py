from __future__ import annotations

from datetime import date
import os

from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.macro import Macro
from app.schemas.macro import MacroCreate, MacroUpdate
from app.schemas.macro_series import MacroPoint
from app.services.cache_utils import build_cache_key, item_to_dict, items_to_dicts
from app.utils.query_params import SortOrder
from etl.fetchers.akshare_macro_client import fetch_akshare_series_rows, is_akshare_macro_key
from etl.fetchers.worldbank_client import get_indicator_series
from etl.transformers.macro import normalize_macro_rows

MACRO_QUERY_CACHE_TTL = 900
WORLD_BANK_SYNC_FETCH_ENABLED = os.getenv("MACRO_ENABLE_WORLD_BANK_SYNC_FETCH", "0").lower() in {"1", "true", "yes"}

WORLD_BANK_INDICATORS: dict[str, str] = {
    "GDP": "NY.GDP.MKTP.CD",
    "CPI": "FP.CPI.TOTL.ZG",
    "UNEMP": "SL.UEM.TOTL.ZS",
    "TRADE": "NE.TRD.GNFS.ZS",
}

WORLD_BANK_COUNTRIES: set[str] = {
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
}


def list_macro(db: Session, start: date | None = None, end: date | None = None, sort: SortOrder = "desc"):
    """List macro indicators."""
    cache_key = build_cache_key("macro:list", start=start, end=end, sort=sort)
    cached = get_json(cache_key)
    if isinstance(cached, list):
        return cached

    query = db.query(Macro)
    if start is not None:
        query = query.filter(Macro.date >= start)
    if end is not None:
        query = query.filter(Macro.date <= end)
    if sort == "asc":
        items = query.order_by(Macro.date.asc()).all()
    else:
        items = query.order_by(Macro.date.desc()).all()
    set_json(cache_key, items_to_dicts(items), ttl=MACRO_QUERY_CACHE_TTL)
    return items


def get_cached_macro(
    as_of: date | None = None,
    start: date | None = None,
    end: date | None = None,
    sort: SortOrder = "desc",
) -> list[dict] | None:
    """Get cached macro data from Redis (if any)."""
    if as_of is None and (start is not None or end is not None):
        return None
    key = "macro:latest" if as_of is None else f"macro:{as_of.isoformat()}"
    payload = get_json(key)
    if not isinstance(payload, dict):
        return None
    items = payload.get("items")
    if isinstance(items, list):
        normalized = []
        for item in items:
            if not isinstance(item, dict):
                continue
            key_value = item.get("key")
            date_value = item.get("date")
            value = item.get("value")
            score = item.get("score")
            if not key_value or not date_value or value is None:
                continue
            try:
                normalized.append(
                    {
                        "key": str(key_value),
                        "date": str(date_value),
                        "value": float(value),
                        "score": None if score is None else float(score),
                    }
                )
            except (TypeError, ValueError):
                continue
        if start is not None:
            normalized = [item for item in normalized if item.get("date") and item["date"] >= start.isoformat()]
        if end is not None:
            normalized = [item for item in normalized if item.get("date") and item["date"] <= end.isoformat()]
        normalized.sort(key=lambda item: item.get("date") or "", reverse=(sort == "desc"))
        return normalized or None
    return None


def _parse_world_bank_series_key(key: str) -> tuple[str, str] | None:
    indicator, separator, country = key.partition(":")
    indicator = indicator.strip().upper()
    country = country.strip().upper()
    if not separator:
        return None
    if indicator not in WORLD_BANK_INDICATORS or country not in WORLD_BANK_COUNTRIES:
        return None
    return indicator, country


def _fetch_world_bank_series_rows(key: str, start: date | None = None, end: date | None = None) -> list[dict]:
    parsed = _parse_world_bank_series_key(key)
    if parsed is None:
        return []
    indicator, country = parsed
    range_end = end or date.today()
    range_start = start or date(1960, 1, 1)
    fetch_start = date(max(1960, range_start.year), 1, 1)
    fetch_end = date(range_end.year, 12, 31)
    if fetch_start > fetch_end:
        return []

    rows = get_indicator_series(country, WORLD_BANK_INDICATORS[indicator], fetch_start, fetch_end)
    if not rows:
        return []
    for row in rows:
        row["key"] = f"{indicator}:{country}"
    return normalize_macro_rows(rows)


def _fetch_remote_macro_series_rows(key: str, start: date | None = None, end: date | None = None) -> list[dict]:
    if is_akshare_macro_key(key):
        return fetch_akshare_series_rows(key, start=start, end=end)
    if WORLD_BANK_SYNC_FETCH_ENABLED:
        return _fetch_world_bank_series_rows(key, start=start, end=end)
    return []


def _upsert_macro_rows(db: Session, rows: list[dict]) -> None:
    if not rows:
        return
    try:
        for row in rows:
            row_key = row.get("key")
            row_date = row.get("date")
            if not row_key or not isinstance(row_date, date):
                continue
            score = row.get("score")
            db.merge(
                Macro(
                    key=str(row_key),
                    date=row_date,
                    value=float(row.get("value") or 0),
                    score=None if score is None else float(score),
                )
            )
        db.commit()
    except Exception:
        db.rollback()
        raise


def _cached_rows_to_points(cached: list[object]) -> list[MacroPoint]:
    items: list[MacroPoint] = []
    for row in cached:
        if not isinstance(row, dict):
            continue
        try:
            items.append(MacroPoint(**row))
        except Exception:
            continue
    return _sort_macro_points(items)


def _orm_rows_to_points(rows: list[Macro]) -> list[MacroPoint]:
    return _sort_macro_points([MacroPoint(date=row.date, value=float(row.value or 0), score=row.score) for row in rows])


def _dict_rows_to_points(rows: list[dict], start: date | None = None, end: date | None = None) -> list[MacroPoint]:
    items: list[MacroPoint] = []
    for row in rows:
        row_date = row.get("date")
        if not isinstance(row_date, date):
            continue
        if start is not None and row_date < start:
            continue
        if end is not None and row_date > end:
            continue
        score = row.get("score")
        items.append(
            MacroPoint(
                date=row_date,
                value=float(row.get("value") or 0),
                score=None if score is None else float(score),
            )
        )
    return _sort_macro_points(items)


def _sort_macro_points(items: list[MacroPoint]) -> list[MacroPoint]:
    return sorted(items, key=lambda item: item.date)


def get_macro_series(db: Session, key: str, start: date | None = None, end: date | None = None):
    """Get macro time series by key."""
    cache_key = build_cache_key("macro:series", key=key, start=start, end=end)
    cached = get_json(cache_key)
    if isinstance(cached, list):
        items = _cached_rows_to_points(cached)
        if items or (_parse_world_bank_series_key(key) is None and not is_akshare_macro_key(key)):
            return items

    query = db.query(Macro).filter(Macro.key == key)
    if start is not None:
        query = query.filter(Macro.date >= start)
    if end is not None:
        query = query.filter(Macro.date <= end)
    rows = query.order_by(Macro.date.asc()).all()
    items = _orm_rows_to_points(rows)

    if not items:
        fetched_rows = _fetch_remote_macro_series_rows(key, start=start, end=end)
        if fetched_rows:
            _upsert_macro_rows(db, fetched_rows)
            items = _dict_rows_to_points(fetched_rows, start=start, end=end)

    set_json(cache_key, [item_to_dict(item) for item in items], ttl=MACRO_QUERY_CACHE_TTL)
    return items


def create_macro(db: Session, payload: MacroCreate):
    item = Macro(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_macro(db: Session, key: str, macro_date: date, payload: MacroUpdate):
    item = db.query(Macro).filter(Macro.key == key, Macro.date == macro_date).first()
    if item is None:
        return None
    data = payload.dict(exclude_unset=True)
    for field, value in data.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def delete_macro(db: Session, key: str, macro_date: date) -> bool:
    item = db.query(Macro).filter(Macro.key == key, Macro.date == macro_date).first()
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
