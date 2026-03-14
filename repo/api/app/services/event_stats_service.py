from __future__ import annotations

from datetime import date

from sqlalchemy import Date, func
from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.events import Event
from app.schemas.event_stats import CountByDateItem, CountBySymbolItem, CountByTypeItem


def _date_bucket(column, granularity: str):
    if granularity == "week":
        return func.date_trunc("week", column).cast(Date)
    if granularity == "month":
        return func.date_trunc("month", column).cast(Date)
    return func.date_trunc("day", column).cast(Date)


def _cache_key(
    symbols: list[str] | None,
    event_types: list[str] | None,
    start: date | None,
    end: date | None,
    granularity: str,
    top_date: int | None,
    top_type: int | None,
    top_symbol: int | None,
) -> str:
    symbols_key = ",".join(sorted(symbols)) if symbols else "all"
    types_key = ",".join(sorted(event_types)) if event_types else "all"
    start_key = start.isoformat() if start else "none"
    end_key = end.isoformat() if end else "none"
    return f"events_stats:{symbols_key}:{types_key}:{start_key}:{end_key}:{granularity}:{top_date or 0}:{top_type or 0}:{top_symbol or 0}"


def get_event_stats(
    db: Session,
    symbols: list[str] | None = None,
    event_types: list[str] | None = None,
    start: date | None = None,
    end: date | None = None,
    granularity: str = "day",
    top_date: int | None = None,
    top_type: int | None = None,
    top_symbol: int | None = None,
):
    cache_key = _cache_key(symbols, event_types, start, end, granularity, top_date, top_type, top_symbol)
    cached = get_json(cache_key)
    if isinstance(cached, dict):
        by_date = cached.get("by_date")
        by_type = cached.get("by_type")
        by_symbol = cached.get("by_symbol")
        if isinstance(by_date, list) and isinstance(by_type, list) and isinstance(by_symbol, list):
            return (
                [CountByDateItem(**item) for item in by_date],
                [CountByTypeItem(**item) for item in by_type],
                [CountBySymbolItem(**item) for item in by_symbol],
            )

    base_query = db.query(Event)
    if symbols:
        base_query = base_query.filter(Event.symbol.in_(symbols))
    if event_types:
        base_query = base_query.filter(Event.type.in_(event_types))
    if start is not None:
        base_query = base_query.filter(Event.date >= start)
    if end is not None:
        base_query = base_query.filter(Event.date <= end)

    bucket = _date_bucket(Event.date, granularity)
    by_date_query = base_query.with_entities(
        bucket.label("date"), func.count().label("count")
    ).group_by(bucket)
    if top_date:
        by_date_query = by_date_query.order_by(func.count().desc()).limit(top_date)
    else:
        by_date_query = by_date_query.order_by(bucket.asc())
    by_date_rows = by_date_query.all()

    by_type_query = base_query.with_entities(
        Event.type.label("type"), func.count().label("count")
    ).group_by(Event.type)
    by_type_query = by_type_query.order_by(func.count().desc())
    if top_type:
        by_type_query = by_type_query.limit(top_type)
    by_type_rows = by_type_query.all()

    by_symbol_query = base_query.with_entities(
        Event.symbol.label("symbol"), func.count().label("count")
    ).group_by(Event.symbol)
    by_symbol_query = by_symbol_query.order_by(func.count().desc())
    if top_symbol:
        by_symbol_query = by_symbol_query.limit(top_symbol)
    by_symbol_rows = by_symbol_query.all()

    by_date_items = [CountByDateItem(date=row.date, count=row.count) for row in by_date_rows]
    by_type_items = [CountByTypeItem(type=row.type, count=row.count) for row in by_type_rows]
    by_symbol_items = [CountBySymbolItem(symbol=row.symbol, count=row.count) for row in by_symbol_rows]
    set_json(
        cache_key,
        {
            "by_date": [item.dict() for item in by_date_items],
            "by_type": [item.dict() for item in by_type_items],
            "by_symbol": [item.dict() for item in by_symbol_items],
        },
    )
    return (by_date_items, by_type_items, by_symbol_items)
