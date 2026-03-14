from __future__ import annotations

from datetime import date

from app.core.cache import get_json
from sqlalchemy.orm import Session

from app.schemas.insider_trade import InsiderTradeOut
from app.models.insider_trade import InsiderTrade
from app.schemas.insider_trade import InsiderTradeCreate, InsiderTradeUpdate
from app.utils.query_params import SortOrder


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
    preloaded = _load_preloaded_insider(symbol, start, end, trade_types, min_shares, max_shares, sort, limit, offset)
    if preloaded is not None:
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
