from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.futures_price import FuturesPrice
from app.services.cache_utils import build_cache_key, items_to_dicts
from app.utils.query_params import SortOrder

FUTURES_CACHE_TTL = 900


def list_futures(
    db: Session,
    symbol: str | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: SortOrder = "desc",
):
    cache_key = build_cache_key(
        "futures:list",
        symbol=symbol.upper() if symbol else None,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
        sort=sort,
    )
    cached = get_json(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("items"), list) and isinstance(cached.get("total"), int):
        return cached["items"], cached["total"]

    query = db.query(FuturesPrice)
    if symbol:
        query = query.filter(FuturesPrice.symbol == symbol.upper())
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
):
    normalized = symbol.upper()
    cache_key = build_cache_key("futures:series", symbol=normalized, start=start, end=end)
    cached = get_json(cache_key)
    if isinstance(cached, list):
        return cached

    query = db.query(FuturesPrice).filter(FuturesPrice.symbol == symbol.upper())
    if start is not None:
        query = query.filter(FuturesPrice.date >= start)
    if end is not None:
        query = query.filter(FuturesPrice.date <= end)
    items = query.order_by(FuturesPrice.date.asc()).all()
    set_json(cache_key, items_to_dicts(items), ttl=FUTURES_CACHE_TTL)
    return items
