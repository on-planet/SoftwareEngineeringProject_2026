from __future__ import annotations

from datetime import date

from sqlalchemy import Date, func
from sqlalchemy.orm import Session

from app.models.events import Event
from app.schemas.event_stats import CountByDateItem, CountBySymbolItem, CountByTypeItem


def _date_bucket(column, granularity: str):
    if granularity == "week":
        return func.date_trunc("week", column).cast(Date)
    if granularity == "month":
        return func.date_trunc("month", column).cast(Date)
    return func.date_trunc("day", column).cast(Date)


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

    return (
        [CountByDateItem(date=row.date, count=row.count) for row in by_date_rows],
        [CountByTypeItem(type=row.type, count=row.count) for row in by_type_rows],
        [CountBySymbolItem(symbol=row.symbol, count=row.count) for row in by_symbol_rows],
    )
