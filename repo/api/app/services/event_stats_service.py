from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.core.typed_cache import cached_call
from app.schemas.event_stats import CountByDateItem, CountBySymbolItem, CountByTypeItem
from app.services.cache_utils import item_to_dict
from app.services.event_feed_service import _build_event_feed_source


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
    return_meta: bool = False,
):
    cache_key = _cache_key(symbols, event_types, start, end, granularity, top_date, top_type, top_symbol)

    def _infer_as_of(payload: dict[str, Any]) -> str | None:
        rows = payload.get("by_date")
        if not isinstance(rows, list) or not rows:
            return None
        dates = [str(item.get("date")) for item in rows if isinstance(item, dict) and item.get("date")]
        return max(dates) if dates else None

    def _should_use_cached(payload: dict[str, Any]) -> bool:
        if not isinstance(payload, dict):
            return False
        return any(
            isinstance(payload.get(key), list) and len(payload.get(key, [])) > 0
            for key in ("by_date", "by_type", "by_symbol")
        )

    def _build_payload() -> dict[str, list[dict[str, Any]]]:
        date_counter: Counter[date] = Counter()
        type_counter: Counter[str] = Counter()
        symbol_counter: Counter[str] = Counter()
        source = _build_event_feed_source(
            symbols=symbols,
            event_types=event_types,
            start=start,
            end=end,
        )
        if source is not None:
            by_day_rows = db.execute(
                select(source.c.date.label("date"), func.count().label("count"))
                .select_from(source)
                .group_by(source.c.date)
            ).all()
            for row in by_day_rows:
                bucket = _date_bucket(row.date, granularity)
                date_counter[bucket] += int(row.count or 0)

            by_type_rows = db.execute(
                select(source.c.type.label("type"), func.count().label("count"))
                .select_from(source)
                .group_by(source.c.type)
            ).all()
            for row in by_type_rows:
                if row.type:
                    type_counter[str(row.type)] += int(row.count or 0)

            by_symbol_rows = db.execute(
                select(source.c.symbol.label("symbol"), func.count().label("count"))
                .select_from(source)
                .group_by(source.c.symbol)
            ).all()
            for row in by_symbol_rows:
                if row.symbol:
                    symbol_counter[str(row.symbol)] += int(row.count or 0)

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

        return {
            "by_date": [item_to_dict(item) for item in by_date_items],
            "by_type": [item_to_dict(item) for item in by_type_items],
            "by_symbol": [item_to_dict(item) for item in by_symbol_items],
        }

    payload, cache_meta = cached_call(
        "event_stats",
        cache_key,
        _build_payload,
        as_of=_infer_as_of,
        should_use_cached=_should_use_cached,
        getter=get_json,
        setter=set_json,
    )

    by_date = [CountByDateItem(**item) for item in payload.get("by_date", []) if isinstance(item, dict)]
    by_type = [CountByTypeItem(**item) for item in payload.get("by_type", []) if isinstance(item, dict)]
    by_symbol = [CountBySymbolItem(**item) for item in payload.get("by_symbol", []) if isinstance(item, dict)]

    if return_meta:
        return by_date, by_type, by_symbol, cache_meta
    return by_date, by_type, by_symbol
