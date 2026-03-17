from __future__ import annotations

from collections import defaultdict
from datetime import date

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.core.cache import get_json
from app.models.daily_prices import DailyPrice
from app.models.stocks import Stock
from app.utils.query_params import SortOrder
from etl.utils.sector_taxonomy import UNKNOWN_SECTOR, normalize_sector_name


def _format_as_of(value) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _coerce_float(value) -> float:
    return float(value or 0.0)


def _coerce_int(value) -> int:
    return int(value or 0)


def _normalize_cached_item(item: dict) -> dict:
    return {
        **item,
        "sector": normalize_sector_name(item.get("sector"), market=item.get("market")),
        "avg_close": _coerce_float(item.get("avg_close")),
        "avg_change": _coerce_float(item.get("avg_change")),
        "close_sum": _coerce_float(item.get("close_sum")),
        "change_sum": _coerce_float(item.get("change_sum")),
        "count": _coerce_int(item.get("count")),
    }


def _aggregate_cached_items(items: list[dict]) -> list[dict] | None:
    buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"close_sum": 0.0, "change_sum": 0.0, "count": 0.0})
    for item in items:
        if item.get("count") is None or item.get("close_sum") is None or item.get("change_sum") is None:
            return None
        sector_name = item["sector"]
        bucket = buckets[sector_name]
        bucket["close_sum"] += _coerce_float(item.get("close_sum"))
        bucket["change_sum"] += _coerce_float(item.get("change_sum"))
        bucket["count"] += float(_coerce_int(item.get("count")))

    aggregated: list[dict] = []
    for sector_name, bucket in buckets.items():
        count = bucket["count"] or 0.0
        aggregated.append(
            {
                "sector": sector_name,
                "avg_close": (bucket["close_sum"] / count) if count else 0.0,
                "avg_change": (bucket["change_sum"] / count) if count else 0.0,
            }
        )
    return aggregated


def get_heatmap(
    db: Session,
    sort: SortOrder = "desc",
    sector: str | None = None,
    market: str | None = None,
    min_change: float | None = None,
    max_change: float | None = None,
    as_of: date | None = None,
):
    sector_filter = normalize_sector_name(sector) if sector else None
    latest_by_symbol = (
        db.query(
            DailyPrice.symbol.label("symbol"),
            func.max(DailyPrice.date).label("latest_date"),
        )
        .join(Stock, DailyPrice.symbol == Stock.symbol)
    )
    if market:
        latest_by_symbol = latest_by_symbol.filter(Stock.market == market)
    if as_of is not None:
        latest_by_symbol = latest_by_symbol.filter(DailyPrice.date <= as_of)
    latest_by_symbol = latest_by_symbol.group_by(DailyPrice.symbol).subquery()

    query = (
        db.query(
            Stock.sector,
            func.sum(DailyPrice.close).label("close_sum"),
            func.sum(DailyPrice.close - DailyPrice.open).label("change_sum"),
            func.count(DailyPrice.symbol).label("symbol_count"),
        )
        .join(
            latest_by_symbol,
            Stock.symbol == latest_by_symbol.c.symbol,
        )
        .join(
            DailyPrice,
            and_(
                DailyPrice.symbol == latest_by_symbol.c.symbol,
                DailyPrice.date == latest_by_symbol.c.latest_date,
            ),
        )
        .group_by(Stock.sector)
    )
    if market:
        query = query.filter(Stock.market == market)
    rows = query.all()

    buckets: dict[str, dict[str, float]] = defaultdict(lambda: {"close_sum": 0.0, "change_sum": 0.0, "count": 0.0})
    for sector_name, close_sum, change_sum, symbol_count in rows:
        normalized_sector = normalize_sector_name(sector_name, market=market)
        bucket = buckets[normalized_sector]
        bucket["close_sum"] += float(close_sum or 0.0)
        bucket["change_sum"] += float(change_sum or 0.0)
        bucket["count"] += float(symbol_count or 0.0)

    results = []
    for sector_name, bucket in buckets.items():
        count = bucket["count"] or 0.0
        avg_close = (bucket["close_sum"] / count) if count else 0.0
        avg_change = (bucket["change_sum"] / count) if count else 0.0
        if sector_filter and sector_name != sector_filter:
            continue
        if min_change is not None and avg_change < min_change:
            continue
        if max_change is not None and avg_change > max_change:
            continue
        results.append({"sector": sector_name, "avg_close": avg_close, "avg_change": avg_change})
    return sorted(results, key=lambda item: item["avg_change"], reverse=(sort == "desc"))


def get_cached_heatmap(
    as_of: date | None = None,
    sector: str | None = None,
    market: str | None = None,
    min_change: float | None = None,
    max_change: float | None = None,
    sort: SortOrder = "desc",
) -> list[dict] | None:
    key = "heatmap:latest" if as_of is None else f"heatmap:{_format_as_of(as_of)}"
    payload = get_json(key)
    if not payload:
        return None
    items = payload.get("items")
    if not isinstance(items, list):
        return None
    if market and items and all("market" not in item for item in items):
        return None
    if items and any("avg_close" not in item for item in items):
        return None

    sector_filter = normalize_sector_name(sector) if sector else None
    normalized = [_normalize_cached_item(item) for item in items]
    if market:
        normalized = [item for item in normalized if item.get("market") == market]
    elif any(item.get("market") for item in normalized):
        aggregated = _aggregate_cached_items(normalized)
        if aggregated is None:
            return None
        normalized = aggregated
    if sector_filter:
        normalized = [item for item in normalized if item["sector"] == sector_filter]
    if min_change is not None:
        normalized = [item for item in normalized if item["avg_change"] >= min_change]
    if max_change is not None:
        normalized = [item for item in normalized if item["avg_change"] <= max_change]
    if normalized and all(item["sector"] == UNKNOWN_SECTOR for item in normalized):
        return None
    return sorted(normalized, key=lambda item: item["avg_change"], reverse=(sort == "desc"))
