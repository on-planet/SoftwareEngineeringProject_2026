from __future__ import annotations

from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.events import Event
from app.schemas.event_timeline import EventTimelineItem


def list_event_timeline(
    db: Session,
    symbols: list[str] | None = None,
    start: date | None = None,
    end: date | None = None,
    event_types: list[str] | None = None,
    keyword: str | None = None,
    sort_by: list[str] | None = None,
    limit: int = 100,
    offset: int = 0,
    sort: str = "desc",
):
    query = db.query(Event)
    if symbols:
        query = query.filter(Event.symbol.in_(symbols))
    if event_types:
        query = query.filter(Event.type.in_(event_types))
    if keyword:
        keyword_like = f"%{keyword}%"
        query = query.filter(
            or_(Event.title.ilike(keyword_like), Event.type.ilike(keyword_like))
        )
    if start is not None:
        query = query.filter(Event.date >= start)
    if end is not None:
        query = query.filter(Event.date <= end)
    total = query.count()
    sort_fields = {
        "date": Event.date,
        "title": Event.title,
        "symbol": Event.symbol,
        "type": Event.type,
    }
    sort_keys = [key for key in (sort_by or ["date"]) if key in sort_fields]
    if not sort_keys:
        sort_keys = ["date"]
    ordering = [
        (sort_fields[key].asc() if sort == "asc" else sort_fields[key].desc())
        for key in sort_keys
    ]
    rows = (
        query.order_by(*ordering)
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [
        EventTimelineItem(
            symbol=row.symbol,
            type=row.type,
            title=row.title,
            date=row.date,
        )
        for row in rows
    ]
    return items, total
