from __future__ import annotations

from datetime import date
import os

from app.core.cache import get_json, set_json
from sqlalchemy.orm import Session

from app.models.buyback import Buyback
from app.schemas.buyback import BuybackCreate, BuybackOut, BuybackUpdate
from app.services.cache_utils import build_cache_key, item_to_dict
from app.utils.query_params import SortOrder

BUYBACK_CACHE_TTL = max(60, int(os.getenv("BUYBACK_CACHE_TTL", "300")))


def _cache_key(
    *,
    symbol: str,
    limit: int,
    offset: int,
    start: date | None,
    end: date | None,
    min_amount: float | None,
    max_amount: float | None,
    sort: SortOrder,
) -> str:
    return build_cache_key(
        "buyback",
        symbol=symbol,
        limit=limit,
        offset=offset,
        start=start,
        end=end,
        min_amount=min_amount,
        max_amount=max_amount,
        sort=sort,
    )


def _load_cached_buyback(
    *,
    symbol: str,
    limit: int,
    offset: int,
    start: date | None,
    end: date | None,
    min_amount: float | None,
    max_amount: float | None,
    sort: SortOrder,
) -> tuple[list[BuybackOut], int] | None:
    payload = get_json(
        _cache_key(
            symbol=symbol,
            limit=limit,
            offset=offset,
            start=start,
            end=end,
            min_amount=min_amount,
            max_amount=max_amount,
            sort=sort,
        )
    )
    if not isinstance(payload, dict):
        return None
    raw_items = payload.get("items")
    total = payload.get("total")
    if not isinstance(raw_items, list) or not isinstance(total, int):
        return None
    items: list[BuybackOut] = []
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        try:
            items.append(BuybackOut(**row))
        except Exception:
            continue
    return items, total


def _cache_buyback(
    items: list[BuybackOut] | list[Buyback],
    total: int,
    *,
    symbol: str,
    limit: int,
    offset: int,
    start: date | None,
    end: date | None,
    min_amount: float | None,
    max_amount: float | None,
    sort: SortOrder,
) -> None:
    if total <= 0 and not items:
        return
    set_json(
        _cache_key(
            symbol=symbol,
            limit=limit,
            offset=offset,
            start=start,
            end=end,
            min_amount=min_amount,
            max_amount=max_amount,
            sort=sort,
        ),
        {
            "items": [item_to_dict(item) for item in items],
            "total": total,
        },
        ttl=BUYBACK_CACHE_TTL,
    )


def _load_preloaded_buyback(
    symbol: str,
    start: date | None,
    end: date | None,
    min_amount: float | None,
    max_amount: float | None,
    sort: SortOrder,
    limit: int,
    offset: int,
):
    if min_amount is not None or max_amount is not None:
        return None
    preload_key = None
    if start is not None and end is not None and start == end:
        preload_key = f"events:{start.isoformat()}"
    elif start is None and end is None:
        preload_key = "events:latest"
    if preload_key is None:
        return None
    payload = get_json(preload_key)
    items = payload.get("buyback") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return None
    output = []
    for item in items:
        if not isinstance(item, dict) or item.get("symbol") != symbol:
            continue
        row_date = item.get("date")
        if start is not None and row_date and row_date < start.isoformat():
            continue
        if end is not None and row_date and row_date > end.isoformat():
            continue
        try:
            output.append(BuybackOut(symbol=symbol, date=row_date, amount=float(item.get("amount") or 0)))
        except Exception:
            continue
    output.sort(key=lambda item: item.date, reverse=(sort == "desc"))
    total = len(output)
    return output[offset : offset + limit], total


def list_buyback(
    db: Session,
    symbol: str,
    limit: int = 50,
    offset: int = 0,
    start: date | None = None,
    end: date | None = None,
    min_amount: float | None = None,
    max_amount: float | None = None,
    sort: SortOrder = "desc",
):
    """List buyback disclosures by symbol."""
    cached = _load_cached_buyback(
        symbol=symbol,
        limit=limit,
        offset=offset,
        start=start,
        end=end,
        min_amount=min_amount,
        max_amount=max_amount,
        sort=sort,
    )
    if cached is not None:
        return cached

    preloaded = _load_preloaded_buyback(symbol, start, end, min_amount, max_amount, sort, limit, offset)
    if preloaded is not None:
        items, total = preloaded
        _cache_buyback(
            items,
            total,
            symbol=symbol,
            limit=limit,
            offset=offset,
            start=start,
            end=end,
            min_amount=min_amount,
            max_amount=max_amount,
            sort=sort,
        )
        return preloaded

    query = db.query(Buyback).filter(Buyback.symbol == symbol)
    if start is not None:
        query = query.filter(Buyback.date >= start)
    if end is not None:
        query = query.filter(Buyback.date <= end)
    if min_amount is not None:
        query = query.filter(Buyback.amount >= min_amount)
    if max_amount is not None:
        query = query.filter(Buyback.amount <= max_amount)
    total = query.count()
    ordering = Buyback.date.asc() if sort == "asc" else Buyback.date.desc()
    items = (
        query.order_by(ordering)
        .offset(offset)
        .limit(limit)
        .all()
    )
    _cache_buyback(
        items,
        total,
        symbol=symbol,
        limit=limit,
        offset=offset,
        start=start,
        end=end,
        min_amount=min_amount,
        max_amount=max_amount,
        sort=sort,
    )
    return items, total


def create_buyback(db: Session, payload: BuybackCreate):
    item = Buyback(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_buyback(db: Session, symbol: str, buyback_date, payload: BuybackUpdate):
    item = (
        db.query(Buyback)
        .filter(Buyback.symbol == symbol, Buyback.date == buyback_date)
        .first()
    )
    if item is None:
        return None
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_buyback(db: Session, symbol: str, buyback_date) -> bool:
    item = (
        db.query(Buyback)
        .filter(Buyback.symbol == symbol, Buyback.date == buyback_date)
        .first()
    )
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
