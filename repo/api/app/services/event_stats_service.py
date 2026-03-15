from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.schemas.event_stats import CountByDateItem, CountBySymbolItem, CountByTypeItem
from app.services.cache_utils import item_to_dict
from app.services.event_feed_service import load_or_backfill_event_feed


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


def _date_bucket(value: date, granularity: str) -> date:
    if granularity == "week":
        return value - timedelta(days=value.weekday())
    if granularity == "month":
        return value.replace(day=1)
    return value


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
            if by_date or by_type or by_symbol:
                return (
                    [CountByDateItem(**item) for item in by_date if isinstance(item, dict)],
                    [CountByTypeItem(**item) for item in by_type if isinstance(item, dict)],
                    [CountBySymbolItem(**item) for item in by_symbol if isinstance(item, dict)],
                )

    items = load_or_backfill_event_feed(
        db,
        symbols=symbols,
        event_types=event_types,
        start=start,
        end=end,
    )

    date_counter: Counter[date] = Counter()
    type_counter: Counter[str] = Counter()
    symbol_counter: Counter[str] = Counter()
    for item in items:
        date_counter[_date_bucket(item.date, granularity)] += 1
        type_counter[item.type] += 1
        symbol_counter[item.symbol] += 1

    if top_date:
        sorted_dates = sorted(date_counter.items(), key=lambda item: (-item[1], item[0]))[:top_date]
    else:
        sorted_dates = sorted(date_counter.items(), key=lambda item: item[0])
    by_date_items = [CountByDateItem(date=bucket, count=count) for bucket, count in sorted_dates]

    sorted_types = sorted(type_counter.items(), key=lambda item: (-item[1], item[0]))
    if top_type:
        sorted_types = sorted_types[:top_type]
    by_type_items = [CountByTypeItem(type=event_type, count=count) for event_type, count in sorted_types]

    sorted_symbols = sorted(symbol_counter.items(), key=lambda item: (-item[1], item[0]))
    if top_symbol:
        sorted_symbols = sorted_symbols[:top_symbol]
    by_symbol_items = [CountBySymbolItem(symbol=symbol, count=count) for symbol, count in sorted_symbols]

    set_json(
        cache_key,
        {
            "by_date": [item_to_dict(item) for item in by_date_items],
            "by_type": [item_to_dict(item) for item in by_type_items],
            "by_symbol": [item_to_dict(item) for item in by_symbol_items],
        },
    )
    return by_date_items, by_type_items, by_symbol_items
