from __future__ import annotations

from datetime import date, timedelta
from threading import Lock, Thread
import os

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
_EVENT_BACKFILL_LOCK = Lock()
_EVENT_BACKFILL_INFLIGHT: set[tuple[date, date]] = set()


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


def _query_event_feed(
    db: Session,
    *,
    symbols: list[str] | None = None,
    event_types: list[str] | None = None,
    keyword: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[EventTimelineItem]:
    items: list[EventTimelineItem] = []

    query = db.query(Event)
    if symbols:
        query = query.filter(Event.symbol.in_(symbols))
    if start is not None:
        query = query.filter(Event.date >= start)
    if end is not None:
        query = query.filter(Event.date <= end)
    for row in query.all():
        item = EventTimelineItem(
            symbol=row.symbol,
            type=row.type,
            title=row.title,
            date=row.date,
            link=getattr(row, "link", None),
            source=getattr(row, "source", None),
        )
        if _matches_filters(item, symbols=symbols, event_types=event_types, keyword=keyword, start=start, end=end):
            items.append(item)

    buyback_query = db.query(Buyback)
    if symbols:
        buyback_query = buyback_query.filter(Buyback.symbol.in_(symbols))
    if start is not None:
        buyback_query = buyback_query.filter(Buyback.date >= start)
    if end is not None:
        buyback_query = buyback_query.filter(Buyback.date <= end)
    for row in buyback_query.all():
        item = EventTimelineItem(
            symbol=row.symbol,
            type="buyback",
            title=_build_buyback_title(row.amount),
            date=row.date,
            source="Buyback",
        )
        if _matches_filters(item, symbols=symbols, event_types=event_types, keyword=keyword, start=start, end=end):
            items.append(item)

    insider_query = db.query(InsiderTrade)
    if symbols:
        insider_query = insider_query.filter(InsiderTrade.symbol.in_(symbols))
    if start is not None:
        insider_query = insider_query.filter(InsiderTrade.date >= start)
    if end is not None:
        insider_query = insider_query.filter(InsiderTrade.date <= end)
    for row in insider_query.all():
        item = EventTimelineItem(
            symbol=row.symbol,
            type="insider",
            title=_build_insider_title(row.type, row.shares),
            date=row.date,
            source="Insider Trade",
        )
        if _matches_filters(item, symbols=symbols, event_types=event_types, keyword=keyword, start=start, end=end):
            items.append(item)

    return items


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
    backfill_mode: str = "sync",
) -> list[EventTimelineItem]:
    cached = _load_cached_event_feed(
        symbols=symbols,
        event_types=event_types,
        keyword=keyword,
        start=start,
        end=end,
    )
    if cached:
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

    items = _query_event_feed(
        db,
        symbols=symbols,
        event_types=event_types,
        keyword=keyword,
        start=start,
        end=end,
    )
    if items:
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

    existing_items = _query_event_feed(
        db,
        start=remote_range[0],
        end=remote_range[1],
    )
    if existing_items:
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

    refreshed_items = _query_event_feed(
        db,
        symbols=symbols,
        event_types=event_types,
        keyword=keyword,
        start=start,
        end=end,
    )
    if refreshed_items:
        _cache_event_feed(
            refreshed_items,
            symbols=symbols,
            event_types=event_types,
            keyword=keyword,
            start=start,
            end=end,
        )
    return refreshed_items
