from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.schemas.event_timeline import EventTimelineItem
from app.services.cache_utils import item_to_dict
from app.services.event_feed_service import load_or_backfill_event_feed, sort_event_feed_items


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
    cache_key = _cache_key(symbols, event_types, keyword, sort_by, start, end, limit, offset, sort)
    cached = get_json(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("items"), list) and isinstance(cached.get("total"), int):
        items = [EventTimelineItem(**item) for item in cached.get("items") if isinstance(item, dict)]
        if items or cached.get("total", 0) > 0:
            return items, cached.get("total")

    items = load_or_backfill_event_feed(
        db,
        symbols=symbols,
        event_types=event_types,
        keyword=keyword,
        start=start,
        end=end,
        backfill_mode="async",
    )
    ordered = sort_event_feed_items(items, sort_by=sort_by, sort=sort)
    total = len(ordered)
    paged = ordered[offset : offset + limit]
    set_json(cache_key, {"items": [item_to_dict(item) for item in paged], "total": total})
    return paged, total
