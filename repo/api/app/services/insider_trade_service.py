from __future__ import annotations

from datetime import date
import os

from app.core.cache import get_json, set_json
from sqlalchemy.orm import Session

from app.models.insider_trade import InsiderTrade
from app.schemas.insider_trade import InsiderTradeCreate, InsiderTradeOut, InsiderTradeUpdate
from app.services.cache_utils import build_cache_key, item_to_dict
from app.utils.query_params import SortOrder

INSIDER_TRADE_CACHE_TTL = max(60, int(os.getenv("INSIDER_TRADE_CACHE_TTL", "300")))


def _cache_key(
    *,
    symbol: str,
    limit: int,
    offset: int,
    start: date | None,
    end: date | None,
    trade_types: list[str] | None,
    min_shares: float | None,
    max_shares: float | None,
    sort: SortOrder,
) -> str:
    return build_cache_key(
        "insider_trade",
        symbol=symbol,
        limit=limit,
        offset=offset,
        start=start,
        end=end,
        trade_types=sorted(trade_types) if trade_types else None,
        min_shares=min_shares,
        max_shares=max_shares,
        sort=sort,
    )


def _load_cached_insider_trades(
    *,
    symbol: str,
    limit: int,
    offset: int,
    start: date | None,
    end: date | None,
    trade_types: list[str] | None,
    min_shares: float | None,
    max_shares: float | None,
    sort: SortOrder,
) -> tuple[list[InsiderTradeOut], int] | None:
    payload = get_json(
        _cache_key(
            symbol=symbol,
            limit=limit,
            offset=offset,
            start=start,
            end=end,
            trade_types=trade_types,
            min_shares=min_shares,
            max_shares=max_shares,
            sort=sort,
        )
    )
    if not isinstance(payload, dict):
        return None
    raw_items = payload.get("items")
    total = payload.get("total")
    if not isinstance(raw_items, list) or not isinstance(total, int):
        return None
    items: list[InsiderTradeOut] = []
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        try:
            items.append(InsiderTradeOut(**row))
        except Exception:
            continue
    return items, total


def _cache_insider_trades(
    items: list[InsiderTradeOut] | list[InsiderTrade],
    total: int,
    *,
    symbol: str,
    limit: int,
    offset: int,
    start: date | None,
    end: date | None,
    trade_types: list[str] | None,
    min_shares: float | None,
    max_shares: float | None,
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
            trade_types=trade_types,
            min_shares=min_shares,
            max_shares=max_shares,
            sort=sort,
        ),
        {
            "items": [item_to_dict(item) for item in items],
            "total": total,
        },
        ttl=INSIDER_TRADE_CACHE_TTL,
    )


def _load_preloaded_insider(
    symbol: str,
    start: date | None,
    end: date | None,
    trade_types: list[str] | None,
    min_shares: float | None,
    max_shares: float | None,
    sort: SortOrder,
    limit: int,
    offset: int,
):
    preload_key = None
    if start is not None and end is not None and start == end:
        preload_key = f"events:{start.isoformat()}"
    elif start is None and end is None:
        preload_key = "events:latest"
    if preload_key is None:
        return None
    payload = get_json(preload_key)
    items = payload.get("insider") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return None
    output = []
    for item in items:
        if not isinstance(item, dict) or item.get("symbol") != symbol:
            continue
        row_date = item.get("date")
        row_type = item.get("type")
        shares = item.get("shares")
        if trade_types and row_type not in trade_types:
            continue
        if start is not None and row_date and row_date < start.isoformat():
            continue
        if end is not None and row_date and row_date > end.isoformat():
            continue
        try:
            shares_value = float(shares or 0)
        except (TypeError, ValueError):
            continue
        if min_shares is not None and shares_value < min_shares:
            continue
        if max_shares is not None and shares_value > max_shares:
            continue
        try:
            output.append(
                InsiderTradeOut(
                    id=None,
                    symbol=symbol,
                    date=row_date,
                    type=str(row_type or ""),
                    shares=shares_value,
                )
            )
        except Exception:
            continue
    output.sort(key=lambda item: item.date, reverse=(sort == "desc"))
    total = len(output)
    return output[offset : offset + limit], total


def list_insider_trades(
    db: Session,
    symbol: str,
    limit: int = 50,
    offset: int = 0,
    start: date | None = None,
    end: date | None = None,
    trade_types: list[str] | None = None,
    min_shares: float | None = None,
    max_shares: float | None = None,
    sort: SortOrder = "desc",
):
    """List insider trades by symbol."""
    cached = _load_cached_insider_trades(
        symbol=symbol,
        limit=limit,
        offset=offset,
        start=start,
        end=end,
        trade_types=trade_types,
        min_shares=min_shares,
        max_shares=max_shares,
        sort=sort,
    )
    if cached is not None:
        return cached

    preloaded = _load_preloaded_insider(symbol, start, end, trade_types, min_shares, max_shares, sort, limit, offset)
    if preloaded is not None:
        items, total = preloaded
        _cache_insider_trades(
            items,
            total,
            symbol=symbol,
            limit=limit,
            offset=offset,
            start=start,
            end=end,
            trade_types=trade_types,
            min_shares=min_shares,
            max_shares=max_shares,
            sort=sort,
        )
        return preloaded

    query = db.query(InsiderTrade).filter(InsiderTrade.symbol == symbol)
    if trade_types:
        query = query.filter(InsiderTrade.type.in_(trade_types))
    if start is not None:
        query = query.filter(InsiderTrade.date >= start)
    if end is not None:
        query = query.filter(InsiderTrade.date <= end)
    if min_shares is not None:
        query = query.filter(InsiderTrade.shares >= min_shares)
    if max_shares is not None:
        query = query.filter(InsiderTrade.shares <= max_shares)
    total = query.count()
    ordering = InsiderTrade.date.asc() if sort == "asc" else InsiderTrade.date.desc()
    items = (
        query.order_by(ordering)
        .offset(offset)
        .limit(limit)
        .all()
    )
    _cache_insider_trades(
        items,
        total,
        symbol=symbol,
        limit=limit,
        offset=offset,
        start=start,
        end=end,
        trade_types=trade_types,
        min_shares=min_shares,
        max_shares=max_shares,
        sort=sort,
    )
    return items, total


def create_insider_trade(db: Session, payload: InsiderTradeCreate):
    item = InsiderTrade(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_insider_trade(db: Session, trade_id: int, payload: InsiderTradeUpdate):
    item = db.query(InsiderTrade).filter(InsiderTrade.id == trade_id).first()
    if item is None:
        return None
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_insider_trade(db: Session, trade_id: int) -> bool:
    item = db.query(InsiderTrade).filter(InsiderTrade.id == trade_id).first()
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
