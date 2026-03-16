from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.futures_price import FuturesPrice
from app.models.futures_weekly_price import FuturesWeeklyPrice
from app.services.cache_utils import build_cache_key, items_to_dicts
from app.utils.query_params import SortOrder
from etl.fetchers.futures_client import get_futures_weekly

FUTURES_CACHE_TTL = 900
DEFAULT_FUTURES_SYMBOLS = ("CU", "AU", "AG", "AO", "SC", "FU")
FuturesFrequency = Literal["day", "week"]


def list_futures(
    db: Session,
    symbol: str | None = None,
    start: date | None = None,
    end: date | None = None,
    as_of: date | None = None,
    frequency: FuturesFrequency = "day",
    limit: int = 50,
    offset: int = 0,
    sort: SortOrder = "desc",
):
    cache_key = build_cache_key(
        "futures:list",
        symbol=symbol.upper() if symbol else None,
        start=start,
        end=end,
        as_of=as_of,
        frequency=frequency,
        limit=limit,
        offset=offset,
        sort=sort,
    )
    cached = get_json(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("items"), list) and isinstance(cached.get("total"), int):
        return cached["items"], cached["total"]

    if frequency == "week":
        snapshot_date = _resolve_weekly_snapshot_date(db, as_of=as_of, end=end)
        if snapshot_date is None:
            items = []
        else:
            items = _query_weekly_snapshot(db, snapshot_date=snapshot_date, symbol=symbol, sort=sort)
        if not items and snapshot_date is not None:
            items = _filter_sort_weekly_rows(get_futures_weekly(snapshot_date), symbol=symbol, sort=sort)
        total = len(items)
        sliced = items[offset : offset + limit]
        set_json(cache_key, {"items": sliced, "total": total}, ttl=FUTURES_CACHE_TTL)
        return sliced, total

    query = db.query(FuturesPrice)
    if symbol:
        query = query.filter(FuturesPrice.symbol == symbol.upper())
    else:
        query = query.filter(FuturesPrice.symbol.in_(DEFAULT_FUTURES_SYMBOLS))
    if start is not None:
        query = query.filter(FuturesPrice.date >= start)
    if end is not None:
        query = query.filter(FuturesPrice.date <= end)

    total = query.count()
    if sort == "asc":
        query = query.order_by(FuturesPrice.date.asc(), FuturesPrice.symbol.asc())
    else:
        query = query.order_by(FuturesPrice.date.desc(), FuturesPrice.symbol.asc())
    items = query.offset(offset).limit(limit).all()
    set_json(cache_key, {"items": items_to_dicts(items), "total": total}, ttl=FUTURES_CACHE_TTL)
    return items, total


def get_futures_series(
    db: Session,
    symbol: str,
    start: date | None = None,
    end: date | None = None,
    frequency: FuturesFrequency = "day",
):
    normalized = symbol.upper()
    cache_key = build_cache_key("futures:series", symbol=normalized, start=start, end=end, frequency=frequency)
    cached = get_json(cache_key)
    if isinstance(cached, list):
        return cached

    if frequency == "week":
        items = _get_weekly_series(db, symbol=normalized, start=start, end=end)
        set_json(cache_key, items, ttl=FUTURES_CACHE_TTL)
        return items

    query = db.query(FuturesPrice).filter(FuturesPrice.symbol == symbol.upper())
    if start is not None:
        query = query.filter(FuturesPrice.date >= start)
    if end is not None:
        query = query.filter(FuturesPrice.date <= end)
    items = query.order_by(FuturesPrice.date.asc()).all()
    set_json(cache_key, items_to_dicts(items), ttl=FUTURES_CACHE_TTL)
    return items


def _normalize_weekly_as_of(as_of: date | None) -> date:
    base = as_of or date.today()
    weekday = base.weekday()
    offset = (weekday - 4) % 7
    return base - timedelta(days=offset)


def _weekly_dates(start: date | None, end: date | None, *, limit: int = 16) -> list[date]:
    latest = _normalize_weekly_as_of(end)
    if start is None:
        start = latest - timedelta(days=(limit - 1) * 7)
    start = _normalize_weekly_as_of(start)
    if start > latest:
        start, latest = latest, start
    output: list[date] = []
    current = start
    while current <= latest:
        output.append(current)
        current += timedelta(days=7)
    return output[-limit:]


def _filter_sort_weekly_rows(rows: list[dict], *, symbol: str | None, sort: SortOrder) -> list[dict]:
    if symbol:
        rows = [row for row in rows if str(row.get("symbol") or "").upper() == symbol.upper()]
    rows = [row for row in rows if str(row.get("symbol") or "").upper() in DEFAULT_FUTURES_SYMBOLS]
    rows.sort(key=lambda row: (str(row.get("symbol") or ""), row.get("date")), reverse=(sort != "asc"))
    if sort == "desc":
        rows.sort(key=lambda row: row.get("date"), reverse=True)
    else:
        rows.sort(key=lambda row: row.get("date"))
    return rows


def _resolve_weekly_snapshot_date(db: Session, as_of: date | None = None, end: date | None = None) -> date | None:
    target = _normalize_weekly_as_of(as_of or end) if (as_of or end) else None
    query = db.query(FuturesWeeklyPrice.date)
    if target is not None:
        match = query.filter(FuturesWeeklyPrice.date == target).order_by(FuturesWeeklyPrice.date.desc()).first()
        if match is not None:
            return _coerce_query_date(match)
        return target
    latest = query.order_by(FuturesWeeklyPrice.date.desc()).first()
    if latest is not None:
        return _coerce_query_date(latest)
    return _normalize_weekly_as_of(date.today())


def _query_weekly_snapshot(
    db: Session,
    *,
    snapshot_date: date,
    symbol: str | None = None,
    sort: SortOrder = "desc",
) -> list[dict]:
    query = db.query(FuturesWeeklyPrice).filter(FuturesWeeklyPrice.date == snapshot_date)
    if symbol:
        query = query.filter(FuturesWeeklyPrice.symbol == symbol.upper())
    else:
        query = query.filter(FuturesWeeklyPrice.symbol.in_(DEFAULT_FUTURES_SYMBOLS))
    if sort == "asc":
        items = query.order_by(FuturesWeeklyPrice.symbol.asc()).all()
    else:
        items = query.order_by(FuturesWeeklyPrice.symbol.asc()).all()
    return items_to_dicts(items)


def _query_weekly_series(db: Session, symbol: str, start: date | None = None, end: date | None = None):
    query = db.query(FuturesWeeklyPrice).filter(FuturesWeeklyPrice.symbol == symbol.upper())
    if start is not None:
        query = query.filter(FuturesWeeklyPrice.date >= _normalize_weekly_as_of(start))
    if end is not None:
        query = query.filter(FuturesWeeklyPrice.date <= _normalize_weekly_as_of(end))
    return query.order_by(FuturesWeeklyPrice.date.asc()).all()


def _get_weekly_series(db: Session, symbol: str, start: date | None = None, end: date | None = None) -> list[dict]:
    stored_items = _query_weekly_series(db, symbol=symbol, start=start, end=end)
    if stored_items:
        return items_to_dicts(stored_items)

    rows: list[dict] = []
    for as_of in _weekly_dates(start, end):
        snapshot = get_futures_weekly(as_of)
        matched = next((item for item in snapshot if str(item.get("symbol") or "").upper() == symbol.upper()), None)
        if matched:
            rows.append(matched)
    rows.sort(key=lambda row: row.get("date"))
    return rows


def _coerce_query_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, tuple) and value:
        candidate = value[0]
        return candidate if isinstance(candidate, date) else None
    if isinstance(value, dict):
        candidate = value.get("date")
        return candidate if isinstance(candidate, date) else None
    if hasattr(value, "_mapping"):
        candidate = dict(value._mapping).get("date")
        return candidate if isinstance(candidate, date) else None
    return None
