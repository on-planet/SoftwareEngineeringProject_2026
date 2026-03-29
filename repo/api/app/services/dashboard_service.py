from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.core.typed_cache import cached_call
from app.services.cache_utils import build_cache_key, item_to_dict, items_to_dicts
from app.services.event_stats_service import get_event_stats
from app.services.futures_service import list_futures
from app.services.heatmap_service import get_cached_heatmap, get_heatmap
from app.services.index_service import list_indices
from app.services.macro_service import list_macro_snapshot
from app.services.news_aggregate_service import list_news_aggregate
from app.services.news_stats_service import get_news_stats

DASHBOARD_OVERVIEW_CACHE_TTL = 300
DASHBOARD_STATS_CACHE_TTL = 300
FUTURES_OVERVIEW_SOURCE_LIMIT = 240


def _build_page(items: list[Any], limit: int, offset: int = 0, total: int | None = None) -> dict[str, Any]:
    sliced = items[offset : offset + limit]
    return {
        "items": items_to_dicts(sliced),
        "total": len(items) if total is None else total,
        "limit": limit,
        "offset": offset,
    }


def _build_stats_section(
    *,
    by_date: list[Any],
    by_type: list[Any] | None = None,
    by_sentiment: list[Any] | None = None,
    by_symbol: list[Any],
) -> dict[str, Any]:
    payload = {
        "by_date": [item_to_dict(item) for item in by_date],
        "by_symbol": [item_to_dict(item) for item in by_symbol],
    }
    if by_type is not None:
        payload["by_type"] = [item_to_dict(item) for item in by_type]
    if by_sentiment is not None:
        payload["by_sentiment"] = [item_to_dict(item) for item in by_sentiment]
    return payload


def _latest_futures_snapshot(rows: list[Any]) -> list[dict[str, Any]]:
    snapshot: list[dict[str, Any]] = []
    seen_symbols: set[str] = set()
    for row in rows:
        item = item_to_dict(row)
        symbol = str(item.get("symbol") or "").upper()
        if not symbol or symbol in seen_symbols:
            continue
        seen_symbols.add(symbol)
        snapshot.append(item)
    return snapshot


def _coerce_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _infer_overview_as_of(payload: dict[str, Any]) -> str | None:
    candidates: list[str] = []
    sections = [
        payload.get("indices", {}).get("items", []),
        payload.get("macro_snapshot", {}).get("items", []),
        payload.get("futures", {}).get("items", []),
        payload.get("top_news", {}).get("items", []),
    ]
    for rows in sections:
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            stamp = _coerce_timestamp(row.get("published_at") or row.get("date"))
            if stamp:
                candidates.append(stamp)
    return max(candidates) if candidates else None


def _infer_stats_as_of(payload: dict[str, Any]) -> str | None:
    candidates: list[str] = []
    for section_name in ("events", "news"):
        section = payload.get(section_name)
        if not isinstance(section, dict):
            continue
        rows = section.get("by_date")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            stamp = _coerce_timestamp(row.get("date"))
            if stamp:
                candidates.append(stamp)
    return max(candidates) if candidates else None


def get_dashboard_overview(
    db: Session,
    *,
    as_of: date | None = None,
    index_limit: int = 20,
    heatmap_limit: int = 24,
    macro_limit: int = 12,
    futures_limit: int = 8,
    news_limit: int = 8,
) -> dict[str, Any]:
    cache_key = build_cache_key(
        "dashboard:overview",
        as_of=as_of,
        index_limit=index_limit,
        heatmap_limit=heatmap_limit,
        macro_limit=macro_limit,
        futures_limit=futures_limit,
        news_limit=news_limit,
    )

    def _build_payload() -> dict[str, Any]:
        index_items = list_indices(db, as_of=as_of, sort="desc")

        heatmap_a = get_cached_heatmap(as_of=as_of, market="A", sort="desc")
        if heatmap_a is None:
            heatmap_a = get_heatmap(db, sort="desc", market="A", as_of=as_of)

        heatmap_hk = get_cached_heatmap(as_of=as_of, market="HK", sort="desc")
        if heatmap_hk is None:
            heatmap_hk = get_heatmap(db, sort="desc", market="HK", as_of=as_of)

        macro_items = list_macro_snapshot(db, as_of=as_of, sort="desc")

        futures_rows, _ = list_futures(
            db,
            end=as_of,
            sort="desc",
            limit=FUTURES_OVERVIEW_SOURCE_LIMIT,
            offset=0,
        )
        futures_snapshot = _latest_futures_snapshot(futures_rows)

        news_result = list_news_aggregate(
            db,
            limit=news_limit,
            offset=0,
            sort="desc",
            sort_by=["published_at"],
            return_meta=True,
        )
        if len(news_result) == 3:
            news_items, news_total, _ = news_result
        else:
            news_items, news_total = news_result

        return {
            "indices": _build_page(index_items, index_limit),
            "heatmap": {
                "a": _build_page(heatmap_a, heatmap_limit),
                "hk": _build_page(heatmap_hk, heatmap_limit),
            },
            "macro_snapshot": _build_page(macro_items, macro_limit),
            "futures": _build_page(futures_snapshot, futures_limit),
            "top_news": _build_page(news_items, news_limit, total=news_total),
        }

    payload, cache_meta = cached_call(
        "dashboard_overview",
        cache_key,
        _build_payload,
        ttl=DASHBOARD_OVERVIEW_CACHE_TTL,
        as_of=_infer_overview_as_of,
        getter=get_json,
        setter=set_json,
    )
    return {
        "schema_version": "dashboard-overview.v1",
        "query": {
            "as_of": as_of,
            "index_limit": index_limit,
            "heatmap_limit": heatmap_limit,
            "macro_limit": macro_limit,
            "futures_limit": futures_limit,
            "news_limit": news_limit,
        },
        **payload,
        **cache_meta,
    }


def get_dashboard_stats_overview(
    db: Session,
    *,
    symbols: list[str] | None = None,
    event_types: list[str] | None = None,
    sentiments: list[str] | None = None,
    start: date | None = None,
    end: date | None = None,
    granularity: str = "day",
    top_date: int | None = None,
    top_type: int | None = None,
    top_sentiment: int | None = None,
    top_symbol: int | None = None,
) -> dict[str, Any]:
    cache_key = build_cache_key(
        "dashboard:stats_overview",
        symbols=symbols,
        event_types=event_types,
        sentiments=sentiments,
        start=start,
        end=end,
        granularity=granularity,
        top_date=top_date,
        top_type=top_type,
        top_sentiment=top_sentiment,
        top_symbol=top_symbol,
    )

    def _build_payload() -> dict[str, Any]:
        event_result = get_event_stats(
            db,
            symbols=symbols,
            event_types=event_types,
            start=start,
            end=end,
            granularity=granularity,
            top_date=top_date,
            top_type=top_type,
            top_symbol=top_symbol,
            return_meta=True,
        )
        if len(event_result) == 4:
            event_by_date, event_by_type, event_by_symbol, _ = event_result
        else:
            event_by_date, event_by_type, event_by_symbol = event_result

        news_result = get_news_stats(
            db,
            symbols=symbols,
            sentiments=sentiments,
            start=start,
            end=end,
            granularity=granularity,
            top_date=top_date,
            top_sentiment=top_sentiment,
            top_symbol=top_symbol,
            return_meta=True,
        )
        if len(news_result) == 4:
            news_by_date, news_by_sentiment, news_by_symbol, _ = news_result
        else:
            news_by_date, news_by_sentiment, news_by_symbol = news_result

        return {
            "events": _build_stats_section(
                by_date=event_by_date,
                by_type=event_by_type,
                by_symbol=event_by_symbol,
            ),
            "news": _build_stats_section(
                by_date=news_by_date,
                by_sentiment=news_by_sentiment,
                by_symbol=news_by_symbol,
            ),
        }

    payload, cache_meta = cached_call(
        "dashboard_stats",
        cache_key,
        _build_payload,
        ttl=DASHBOARD_STATS_CACHE_TTL,
        as_of=_infer_stats_as_of,
        getter=get_json,
        setter=set_json,
    )
    return {
        "schema_version": "dashboard-stats-overview.v1",
        "query": {
            "symbols": symbols or [],
            "event_types": event_types or [],
            "sentiments": sentiments or [],
            "start": start,
            "end": end,
            "granularity": granularity,
            "top_date": top_date,
            "top_type": top_type,
            "top_sentiment": top_sentiment,
            "top_symbol": top_symbol,
        },
        **payload,
        **cache_meta,
    }
