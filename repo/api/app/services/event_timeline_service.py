from __future__ import annotations

from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.events import Event
from app.schemas.event_timeline import EventTimelineItem


def _cache_key(
    symbols: list[str] | None,
    event_types: list[str] | None,
    keyword: str | None,
    sort_by: list[str] | None,
    start: date | None,
    end: date | None,
    limit: int,
    offset: int,
    sort: str,
) -> str:
    symbols_key = ",".join(sorted(symbols)) if symbols else "all"
    types_key = ",".join(sorted(event_types)) if event_types else "all"
    keyword_key = keyword or "none"
    sort_by_key = ",".join(sort_by or []) or "date"
    start_key = start.isoformat() if start else "none"
    end_key = end.isoformat() if end else "none"
    return f"events_timeline:{symbols_key}:{types_key}:{keyword_key}:{sort_by_key}:{start_key}:{end_key}:{limit}:{offset}:{sort}"


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
    if symbols is None and event_types is None and keyword is None and sort_by in (None, [], ["date"]):
        preload_key = None
        if start is not None and end is not None and start == end:
            preload_key = f"events:{start.isoformat()}"
        elif start is None and end is None:
            preload_key = "events:latest"
        if preload_key:
            preload = get_json(preload_key)
            preload_items = preload.get("items") if isinstance(preload, dict) else None
            if isinstance(preload_items, list):
                items = [
                    EventTimelineItem(**item)
                    for item in preload_items
                    if (start is None or item.get("date") >= start.isoformat())
                    and (end is None or item.get("date") <= end.isoformat())
                ]
                items.sort(key=lambda item: item.date, reverse=(sort == "desc"))
                total = len(items)
                return items[offset : offset + limit], total

    cache_key = _cache_key(symbols, event_types, keyword, sort_by, start, end, limit, offset, sort)
    cached = get_json(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("items"), list) and isinstance(cached.get("total"), int):
        items = [EventTimelineItem(**item) for item in cached.get("items")]
        return items, cached.get("total")

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
            link=getattr(row, "link", None),
            source=getattr(row, "source", None),
        )
        for row in rows
    ]
    set_json(cache_key, {"items": [item.dict() for item in items], "total": total})
    return items, total
