from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.cache import get_json
from app.models.daily_prices import DailyPrice
from app.models.stocks import Stock
from app.utils.query_params import SortOrder


def _format_as_of(value) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def get_heatmap(
    db: Session,
    sort: SortOrder = "desc",
    sector: str | None = None,
    market: str | None = None,
    min_change: float | None = None,
    max_change: float | None = None,
):
    """Get industry heatmap data.

    Aggregate latest close and average change by sector.
    """
    latest_date = db.query(func.max(DailyPrice.date)).scalar()
    if latest_date is None:
        return []
    query = (
        db.query(
            Stock.sector,
            func.avg(DailyPrice.close).label("avg_close"),
            func.avg(DailyPrice.close - DailyPrice.open).label("avg_change"),
        )
        .join(DailyPrice, DailyPrice.symbol == Stock.symbol)
        .filter(DailyPrice.date == latest_date)
        .group_by(Stock.sector)
    )
    if sector:
        query = query.filter(Stock.sector == sector)
    if market:
        query = query.filter(Stock.market == market)
    if min_change is not None:
        query = query.having(func.avg(DailyPrice.close - DailyPrice.open) >= min_change)
    if max_change is not None:
        query = query.having(func.avg(DailyPrice.close - DailyPrice.open) <= max_change)
    rows = query.all()
    results = [
        {
            "sector": sector_name,
            "avg_close": float(avg_close or 0),
            "avg_change": float(avg_change or 0),
        }
        for sector_name, avg_close, avg_change in rows
    ]
    return sorted(results, key=lambda x: x["avg_change"], reverse=(sort == "desc"))


def get_cached_heatmap(
    as_of: date | None = None,
    sector: str | None = None,
    market: str | None = None,
    min_change: float | None = None,
    max_change: float | None = None,
    sort: SortOrder = "desc",
) -> list[dict] | None:
    """Get cached heatmap data from Redis (if any)."""
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
    if sector:
        items = [item for item in items if item.get("sector") == sector]
    if min_change is not None:
        items = [item for item in items if (item.get("avg_change") or 0) >= min_change]
    if max_change is not None:
        items = [item for item in items if (item.get("avg_change") or 0) <= max_change]
    if market:
        items = [item for item in items if item.get("market") == market]
    if not items:
        return items
    normalized = []
    for item in items:
        normalized.append(
            {
                **item,
                "avg_close": float(item.get("avg_close") or 0),
                "avg_change": float(item.get("avg_change") or 0),
            }
        )
    return sorted(normalized, key=lambda x: x["avg_change"], reverse=(sort == "desc"))
