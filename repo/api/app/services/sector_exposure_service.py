from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.cache import get_json
from app.models.daily_prices import DailyPrice
from app.models.stocks import Stock
from app.schemas.sector_exposure import SectorExposureItemOut


def _normalize_items(items: list[dict]) -> list[SectorExposureItemOut]:
    return [
        SectorExposureItemOut(
            sector=item.get("sector"),
            value=float(item.get("value") or 0),
            weight=float(item.get("weight") or 0),
        )
        for item in items
    ]


def get_sector_exposure(
    db: Session,
    market: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    sort: str = "desc",
    as_of: str | None = None,
):
    """Get sector exposure based on latest close aggregation."""
    cache_key = "sector_exposure:latest" if as_of is None else f"sector_exposure:{as_of}"
    cached = get_json(cache_key) or {}
    cached_items = cached.get("items") if isinstance(cached, dict) else None
    if isinstance(cached_items, list) and cached_items:
        items = _normalize_items(cached_items)
    else:
        latest_date = db.query(func.max(DailyPrice.date)).scalar()
        if latest_date is None:
            return []
        query = (
            db.query(
                Stock.sector,
                func.sum(DailyPrice.close).label("total_value"),
            )
            .join(DailyPrice, DailyPrice.symbol == Stock.symbol)
            .filter(DailyPrice.date == latest_date)
            .group_by(Stock.sector)
        )
        if market:
            query = query.filter(Stock.market == market)
        rows = query.all()
        total = sum(float(value or 0) for _, value in rows)
        items = [
            SectorExposureItemOut(
                sector=sector,
                value=float(value or 0),
                weight=(float(value or 0) / total) if total else 0.0,
            )
            for sector, value in rows
        ]
    items.sort(key=lambda x: x.weight, reverse=(sort == "desc"))
    if offset:
        items = items[offset:]
    if limit is not None:
        items = items[:limit]
    return items
