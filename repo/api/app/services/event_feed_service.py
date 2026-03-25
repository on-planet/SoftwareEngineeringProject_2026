from __future__ import annotations

from datetime import date, timedelta
from threading import Lock, Thread
import os
from typing import Literal

from sqlalchemy import Float, String, cast, func, literal, null, or_, select, union_all
from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.buyback import Buyback
from app.models.events import Event
from app.models.insider_trade import InsiderTrade
from app.schemas.event_timeline import EventTimelineItem
from app.services.cache_utils import build_cache_key, item_to_dict
from etl.jobs.events_job import run_events_job

EVENT_REMOTE_LOOKBACK_DAYS = max(1, int(os.getenv("EVENT_REMOTE_LOOKBACK_DAYS", "30")))
EVENT_REMOTE_MAX_RANGE_DAYS = max(1, int(os.getenv("EVENT_REMOTE_MAX_RANGE_DAYS", "31")))
EVENT_FEED_CACHE_TTL = max(60, int(os.getenv("EVENT_FEED_CACHE_TTL", "300")))
EVENT_FEED_QUERY_LIMIT = max(50, int(os.getenv("EVENT_FEED_QUERY_LIMIT", "200")))
_EVENT_BACKFILL_LOCK = Lock()
_EVENT_BACKFILL_INFLIGHT: set[tuple[date, date]] = set()
BUYBACK_EVENT_TYPE = "buyback"
INSIDER_EVENT_TYPE = "insider"
BUYBACK_TITLE_BASE = "\u80a1\u4efd\u56de\u8d2d\u62ab\u9732"
INSIDER_TITLE_BASE = "\u9ad8\u7ba1\u6301\u80a1\u53d8\u52a8"
EventBackfillMode = Literal["off", "async", "sync"]


def _typed_null(sql_type):
    return cast(null(), sql_type)


def _matches_filters(
    item: EventTimelineItem,
    *,
    symbols: list[str] | None = None,
    event_types: list[str] | None = None,
    keyword: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> bool:
    if symbols and item.symbol not in symbols:
        return False
    if event_types and item.type not in event_types:
        return False
    if start is not None and item.date < start:
        return False
    if end is not None and item.date > end:
        return False
    if keyword:
        needle = keyword.strip().lower()
        haystack = f"{item.title} {item.type} {item.symbol}".lower()
        if needle and needle not in haystack:
            return False
    return True


def _build_buyback_title(amount: float | None) -> str:
    if amount is None or amount <= 0:
        return "股份回购披露"
    if amount >= 1:
        return f"股份回购披露 {amount:,.0f}"
    return f"股份回购披露 {amount:,.2f}"


def _build_insider_title(raw_type: str | None, shares: float | None) -> str:
    suffix = str(raw_type or "").strip()
    prefix = "高管持股变动"
    if shares is None or shares == 0:
        return f"{prefix}{f' {suffix}' if suffix else ''}".strip()
    if abs(shares) >= 1:
        shares_text = f"{shares:,.0f}"
    else:
        shares_text = f"{shares:,.2f}"
    return f"{prefix}{f' {suffix}' if suffix else ''} {shares_text}".strip()


def _normalize_requested_event_types(event_types: list[str] | None) -> set[str] | None:
    normalized = {str(item or "").strip() for item in (event_types or []) if str(item or "").strip()}
    return normalized or None


def _build_event_feed_source(
    *,
    symbols: list[str] | None = None,
    event_types: list[str] | None = None,
    start: date | None = None,
    end: date | None = None,
):
    requested_types = _normalize_requested_event_types(event_types)
    standard_event_types = sorted(
        item for item in (requested_types or set()) if item not in {BUYBACK_EVENT_TYPE, INSIDER_EVENT_TYPE}
    )
    selects = []

    include_event_rows = requested_types is None or bool(standard_event_types)
    if include_event_rows:
        event_query = select(
            cast(Event.symbol, String).label("symbol"),
            cast(Event.type, String).label("type"),
            cast(Event.title, String).label("title"),
            Event.date.label("date"),
            cast(Event.link, String).label("link"),
            cast(Event.source, String).label("source"),
            _typed_null(Float).label("amount"),
            _typed_null(String).label("raw_type"),
            _typed_null(Float).label("shares"),
        ).where(
            Event.symbol.is_not(None),
            Event.type.is_not(None),
            Event.date.is_not(None),
        )
        if symbols:
            event_query = event_query.where(Event.symbol.in_(symbols))
        if standard_event_types:
            event_query = event_query.where(Event.type.in_(standard_event_types))
        if start is not None:
            event_query = event_query.where(Event.date >= start)
        if end is not None:
            event_query = event_query.where(Event.date <= end)
        selects.append(event_query)

    if requested_types is None or BUYBACK_EVENT_TYPE in requested_types:
        buyback_query = select(
            cast(Buyback.symbol, String).label("symbol"),
            literal(BUYBACK_EVENT_TYPE, type_=String).label("type"),
            literal(BUYBACK_TITLE_BASE, type_=String).label("title"),
            Buyback.date.label("date"),
            _typed_null(String).label("link"),
            literal("Buyback", type_=String).label("source"),
            cast(Buyback.amount, Float).label("amount"),
            _typed_null(String).label("raw_type"),
            _typed_null(Float).label("shares"),
        ).where(
            Buyback.symbol.is_not(None),
            Buyback.date.is_not(None),
        )
        if symbols:
            buyback_query = buyback_query.where(Buyback.symbol.in_(symbols))
        if start is not None:
            buyback_query = buyback_query.where(Buyback.date >= start)
        if end is not None:
            buyback_query = buyback_query.where(Buyback.date <= end)
        selects.append(buyback_query)

    if requested_types is None or INSIDER_EVENT_TYPE in requested_types:
        insider_query = select(
            cast(InsiderTrade.symbol, String).label("symbol"),
            literal(INSIDER_EVENT_TYPE, type_=String).label("type"),
            literal(INSIDER_TITLE_BASE, type_=String).label("title"),
            InsiderTrade.date.label("date"),
            _typed_null(String).label("link"),
            literal("Insider Trade", type_=String).label("source"),
            _typed_null(Float).label("amount"),
            cast(InsiderTrade.type, String).label("raw_type"),
            cast(InsiderTrade.shares, Float).label("shares"),
        ).where(
            InsiderTrade.symbol.is_not(None),
            InsiderTrade.date.is_not(None),
        )
        if symbols:
            insider_query = insider_query.where(InsiderTrade.symbol.in_(symbols))
        if start is not None:
            insider_query = insider_query.where(InsiderTrade.date >= start)
        if end is not None:
            insider_query = insider_query.where(InsiderTrade.date <= end)
        selects.append(insider_query)

    if not selects:
        return None
    if len(selects) == 1:
        return selects[0].subquery("event_feed")
    return union_all(*selects).subquery("event_feed")


def _apply_keyword_filter(query, source, keyword: str | None):
    needle = str(keyword or "").strip()
    if not needle:
        return query
    keyword_like = f"%{needle}%"
    return query.where(
        or_(
            source.c.title.ilike(keyword_like),
            source.c.type.ilike(keyword_like),
            source.c.symbol.ilike(keyword_like),
            source.c.source.ilike(keyword_like),
            func.coalesce(source.c.raw_type, "").ilike(keyword_like),
        )
    )


def _event_feed_ordering(source, sort_by: list[str] | None = None, sort: str = "desc") -> list:
    sort_fields = {
        "date": source.c.date,
        "title": source.c.title,
        "symbol": source.c.symbol,
        "type": source.c.type,
    }
    sort_keys = [key for key in (sort_by or ["date"]) if key in sort_fields]
    if not sort_keys:
        sort_keys = ["date"]
    reverse = sort == "desc"
    ordering = [
        (sort_fields[key].desc() if reverse else sort_fields[key].asc())
        for key in sort_keys
    ]
    for fallback_key in ("date", "symbol", "type", "title"):
        if fallback_key in sort_keys:
            continue
        ordering.append(sort_fields[fallback_key].desc() if reverse else sort_fields[fallback_key].asc())
    return ordering


def _row_to_event_timeline_item(row) -> EventTimelineItem:
    mapping = row._mapping if hasattr(row, "_mapping") else row
    event_type = str(mapping.get("type") or "")
    if event_type == BUYBACK_EVENT_TYPE:
        title = _build_buyback_title(None if mapping.get("amount") is None else float(mapping.get("amount")))
    elif event_type == INSIDER_EVENT_TYPE:
        shares = None if mapping.get("shares") is None else float(mapping.get("shares"))
        title = _build_insider_title(mapping.get("raw_type"), shares)
    else:
        title = str(mapping.get("title") or "")
    return EventTimelineItem(
        symbol=str(mapping.get("symbol") or ""),
        type=event_type,
        title=title,
        date=mapping.get("date"),
        link=mapping.get("link"),
        source=mapping.get("source"),
    )


def count_event_feed_rows(
    db: Session,
    *,
    symbols: list[str] | None = None,
    event_types: list[str] | None = None,
    keyword: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> int:
    source = _build_event_feed_source(symbols=symbols, event_types=event_types, start=start, end=end)
    if source is None:
        return 0
    query = select(func.count()).select_from(source)
    query = _apply_keyword_filter(query, source, keyword)
    return int(db.execute(query).scalar() or 0)


def list_event_feed_page(
    db: Session,
    *,
    symbols: list[str] | None = None,
    event_types: list[str] | None = None,
    keyword: str | None = None,
    start: date | None = None,
    end: date | None = None,
    sort_by: list[str] | None = None,
    limit: int | None = 100,
    offset: int = 0,
    sort: str = "desc",
) -> tuple[list[EventTimelineItem], int]:
    source = _build_event_feed_source(symbols=symbols, event_types=event_types, start=start, end=end)
    if source is None:
        return [], 0

    query = select(
        source.c.symbol,
        source.c.type,
        source.c.title,
        source.c.date,
        source.c.link,
        source.c.source,
        source.c.amount,
        source.c.raw_type,
        source.c.shares,
        func.count().over().label("_total_count"),
    ).select_from(source)
    query = _apply_keyword_filter(query, source, keyword)
    query = query.order_by(*_event_feed_ordering(source, sort_by=sort_by, sort=sort))
    if offset:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    rows = db.execute(query).all()
    if rows:
        mapping = rows[0]._mapping if hasattr(rows[0], "_mapping") else rows[0]
        total = int(mapping.get("_total_count") or 0)
        return [_row_to_event_timeline_item(row) for row in rows], total
    if offset <= 0:
        return [], 0

    total = count_event_feed_rows(
        db,
        symbols=symbols,
        event_types=event_types,
        keyword=keyword,
        start=start,
        end=end,
    )
    return [], total


def _payload_to_items(
    payload: dict,
    *,
    symbols: list[str] | None = None,
    event_types: list[str] | None = None,
    keyword: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[EventTimelineItem]:
    items: list[EventTimelineItem] = []

    for row in payload.get("items") or []:
        if not isinstance(row, dict):
            continue
        try:
            item = EventTimelineItem(
                symbol=str(row.get("symbol") or ""),
                type=str(row.get("type") or ""),
                title=str(row.get("title") or ""),
                date=row.get("date"),
                link=row.get("link"),
                source=row.get("source"),
            )
        except Exception:
            continue
        if _matches_filters(item, symbols=symbols, event_types=event_types, keyword=keyword, start=start, end=end):
            items.append(item)

    for row in payload.get("buyback") or []:
        if not isinstance(row, dict):
            continue
        try:
            amount = None if row.get("amount") is None else float(row.get("amount"))
            item = EventTimelineItem(
                symbol=str(row.get("symbol") or ""),
                type="buyback",
                title=_build_buyback_title(amount),
                date=row.get("date"),
                link=row.get("link"),
                source=row.get("source") or "Buyback",
            )
        except Exception:
            continue
        if _matches_filters(item, symbols=symbols, event_types=event_types, keyword=keyword, start=start, end=end):
            items.append(item)

    for row in payload.get("insider") or []:
        if not isinstance(row, dict):
            continue
        try:
            shares = None if row.get("shares") is None else float(row.get("shares"))
            item = EventTimelineItem(
                symbol=str(row.get("symbol") or ""),
                type="insider",
                title=_build_insider_title(str(row.get("type") or ""), shares),
                date=row.get("date"),
                link=row.get("link"),
                source=row.get("source") or "Insider Trade",
            )
        except Exception:
            continue
        if _matches_filters(item, symbols=symbols, event_types=event_types, keyword=keyword, start=start, end=end):
            items.append(item)

    return items


def load_preloaded_event_feed(
    *,
    symbols: list[str] | None = None,
    event_types: list[str] | None = None,
    keyword: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[EventTimelineItem] | None:
    preload_key = None
    if start is not None and end is not None and start == end:
        preload_key = f"events:{start.isoformat()}"
    if preload_key is None:
        return None
    payload = get_json(preload_key)
    if not isinstance(payload, dict):
        return None
    return _payload_to_items(
        payload,
        symbols=symbols,
        event_types=event_types,
        keyword=keyword,
        start=start,
        end=end,
    )


def _cache_key(
    *,
    symbols: list[str] | None = None,
    event_types: list[str] | None = None,
    keyword: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> str:
    return build_cache_key(
        "event_feed",
        symbols=sorted(symbols) if symbols else None,
        event_types=sorted(event_types) if event_types else None,
        keyword=keyword,
        start=start,
        end=end,
    )


def _load_cached_event_feed(
    *,
    symbols: list[str] | None = None,
    event_types: list[str] | None = None,
    keyword: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[EventTimelineItem] | None:
    payload = get_json(
        _cache_key(
            symbols=symbols,
            event_types=event_types,
            keyword=keyword,
            start=start,
            end=end,
        )
    )
    if not isinstance(payload, list):
        return None
    items: list[EventTimelineItem] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        try:
            items.append(EventTimelineItem(**row))
        except Exception:
            continue
    return items


def _cache_event_feed(
    items: list[EventTimelineItem],
    *,
    symbols: list[str] | None = None,
    event_types: list[str] | None = None,
    keyword: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> None:
    set_json(
        _cache_key(
            symbols=symbols,
            event_types=event_types,
            keyword=keyword,
            start=start,
            end=end,
        ),
        [item_to_dict(item) for item in items],
        ttl=EVENT_FEED_CACHE_TTL,
    )


def _query_event_feed_preview(
    db: Session,
    *,
    symbols: list[str] | None = None,
    event_types: list[str] | None = None,
    keyword: str | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = EVENT_FEED_QUERY_LIMIT,
) -> tuple[list[EventTimelineItem], int]:
    return list_event_feed_page(
        db,
        symbols=symbols,
        event_types=event_types,
        keyword=keyword,
        start=start,
        end=end,
        limit=limit,
        offset=0,
        sort="desc",
    )


def _query_event_feed(
    db: Session,
    *,
    symbols: list[str] | None = None,
    event_types: list[str] | None = None,
    keyword: str | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = EVENT_FEED_QUERY_LIMIT,
) -> list[EventTimelineItem]:
    items, _ = _query_event_feed_preview(
        db,
        symbols=symbols,
        event_types=event_types,
        keyword=keyword,
        start=start,
        end=end,
        limit=limit,
    )
    return items


def _event_feed_exists(
    db: Session,
    *,
    symbols: list[str] | None = None,
    event_types: list[str] | None = None,
    keyword: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> bool:
    source = _build_event_feed_source(symbols=symbols, event_types=event_types, start=start, end=end)
    if source is None:
        return False
    query = select(literal(1)).select_from(source)
    query = _apply_keyword_filter(query, source, keyword)
    return db.execute(query.limit(1)).first() is not None


def sort_event_feed_items(items: list[EventTimelineItem], sort_by: list[str] | None = None, sort: str = "desc") -> list[EventTimelineItem]:
    sort_fields = {
        "date": lambda item: item.date,
        "title": lambda item: item.title,
        "symbol": lambda item: item.symbol,
        "type": lambda item: item.type,
    }
    ordered = list(items)
    sort_keys = [key for key in (sort_by or ["date"]) if key in sort_fields]
    if not sort_keys:
        sort_keys = ["date"]
    reverse = sort == "desc"
    for key in reversed(sort_keys):
        ordered.sort(key=sort_fields[key], reverse=reverse)
    return ordered


def _has_recent_items(items: list[EventTimelineItem], *, lookback_days: int = 1) -> bool:
    cutoff = date.today() - timedelta(days=max(0, lookback_days))
    return any(item.date >= cutoff for item in items)


def _remote_range(start: date | None = None, end: date | None = None) -> tuple[date, date] | None:
    range_end = end or date.today()
    range_start = start or (range_end - timedelta(days=EVENT_REMOTE_LOOKBACK_DAYS - 1))
    if range_start > range_end:
        return None
    if (range_end - range_start).days + 1 > EVENT_REMOTE_MAX_RANGE_DAYS:
        return None
    return range_start, range_end


def _schedule_remote_backfill(start: date, end: date) -> bool:
    task = (start, end)
    with _EVENT_BACKFILL_LOCK:
        if task in _EVENT_BACKFILL_INFLIGHT:
            return False
        _EVENT_BACKFILL_INFLIGHT.add(task)

    def _runner() -> None:
        try:
            run_events_job(start, end)
        finally:
            with _EVENT_BACKFILL_LOCK:
                _EVENT_BACKFILL_INFLIGHT.discard(task)

    Thread(target=_runner, name=f"events-backfill-{start.isoformat()}-{end.isoformat()}", daemon=True).start()
    return True


def load_or_backfill_event_feed(
    db: Session,
    *,
    symbols: list[str] | None = None,
    event_types: list[str] | None = None,
    keyword: str | None = None,
    start: date | None = None,
    end: date | None = None,
    backfill_mode: EventBackfillMode = "off",
) -> list[EventTimelineItem]:
    cached = _load_cached_event_feed(
        symbols=symbols,
        event_types=event_types,
        keyword=keyword,
        start=start,
        end=end,
    )
    if cached:
        if start is None and end is None and not _has_recent_items(cached, lookback_days=1):
            pass
        else:
            return cached

    preloaded = load_preloaded_event_feed(
        symbols=symbols,
        event_types=event_types,
        keyword=keyword,
        start=start,
        end=end,
    )
    if preloaded:
        _cache_event_feed(
            preloaded,
            symbols=symbols,
            event_types=event_types,
            keyword=keyword,
            start=start,
            end=end,
        )
        return preloaded

    items, total = _query_event_feed_preview(
        db,
        symbols=symbols,
        event_types=event_types,
        keyword=keyword,
        start=start,
        end=end,
    )
    if items:
        if total <= EVENT_FEED_QUERY_LIMIT:
            _cache_event_feed(
                items,
                symbols=symbols,
                event_types=event_types,
                keyword=keyword,
                start=start,
                end=end,
            )
        return items

    remote_range = _remote_range(start=start, end=end)
    if remote_range is None:
        return items

    has_existing_rows = _event_feed_exists(
        db,
        start=remote_range[0],
        end=remote_range[1],
    )
    if has_existing_rows:
        return items

    if backfill_mode == "off":
        return items
    if backfill_mode == "async":
        _schedule_remote_backfill(*remote_range)
        return items

    run_events_job(*remote_range)

    refreshed = load_preloaded_event_feed(
        symbols=symbols,
        event_types=event_types,
        keyword=keyword,
        start=start,
        end=end,
    )
    if refreshed:
        _cache_event_feed(
            refreshed,
            symbols=symbols,
            event_types=event_types,
            keyword=keyword,
            start=start,
            end=end,
        )
        return refreshed

    refreshed_items, refreshed_total = _query_event_feed_preview(
        db,
        symbols=symbols,
        event_types=event_types,
        keyword=keyword,
        start=start,
        end=end,
    )
    if refreshed_items and refreshed_total <= EVENT_FEED_QUERY_LIMIT:
        _cache_event_feed(
            refreshed_items,
            symbols=symbols,
            event_types=event_types,
            keyword=keyword,
            start=start,
            end=end,
        )
    return refreshed_items
