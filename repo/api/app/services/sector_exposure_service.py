from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.cache import get_json
from app.models.sector_exposure import SectorExposure
from app.models.sector_exposure_summary import SectorExposureSummary
from app.schemas.sector_exposure import SectorExposureItemOut, SectorExposureOut

DEFAULT_SECTOR_EXPOSURE_BASIS = "market_value"
UNKNOWN_SECTOR_LABEL = "未分类"


def _normalize_items(items: list[dict]) -> list[SectorExposureItemOut]:
    return [
        SectorExposureItemOut(
            sector=str(item.get("sector") or UNKNOWN_SECTOR_LABEL),
            value=float(item.get("value") or 0),
            weight=float(item.get("weight") or 0),
            symbol_count=int(item.get("symbol_count") or 0),
        )
        for item in items
    ]


def _coerce_date(value: str | date | None) -> date | None:
    if value is None or isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def get_sector_exposure(
    db: Session,
    market: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    sort: str = "desc",
    as_of: str | None = None,
    basis: str = DEFAULT_SECTOR_EXPOSURE_BASIS,
):
    suffix = f":{market}" if market else ""
    cache_key = f"sector_exposure:latest:{basis}{suffix}" if as_of is None else f"sector_exposure:{as_of}:{basis}{suffix}"
    cached = get_json(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("items"), list):
        items = _normalize_items(cached["items"])
        items.sort(key=lambda item: item.weight, reverse=(sort == "desc"))
        if offset:
            items = items[offset:]
        if limit is not None:
            items = items[:limit]
        return SectorExposureOut(
            market=market,
            as_of=_coerce_date(cached.get("date") or as_of),
            basis=str(cached.get("basis") or basis),
            total_value=float(cached.get("total_value") or 0),
            coverage=float(cached.get("coverage") or 0),
            unknown_weight=float(cached.get("unknown_weight") or 0),
            items=items,
        )

    target_market = market or "ALL"
    target_date = _coerce_date(as_of)
    if target_date is None:
        target_date = (
            db.query(func.max(SectorExposureSummary.date))
            .filter(SectorExposureSummary.market == target_market, SectorExposureSummary.basis == basis)
            .scalar()
        )
    if target_date is None:
        return SectorExposureOut(market=market, basis=basis, items=[])

    summary = (
        db.query(SectorExposureSummary)
        .filter(
            SectorExposureSummary.date == target_date,
            SectorExposureSummary.market == target_market,
            SectorExposureSummary.basis == basis,
        )
        .first()
    )
    rows = (
        db.query(SectorExposure)
        .filter(
            SectorExposure.date == target_date,
            SectorExposure.market == target_market,
            SectorExposure.basis == basis,
        )
        .all()
    )
    items = [
        SectorExposureItemOut(
            sector=str(row.sector or UNKNOWN_SECTOR_LABEL),
            value=float(row.value or 0),
            weight=float(row.weight or 0),
            symbol_count=int(row.symbol_count or 0),
        )
        for row in rows
    ]
    items.sort(key=lambda item: item.weight, reverse=(sort == "desc"))
    if offset:
        items = items[offset:]
    if limit is not None:
        items = items[:limit]

    total_value = float(summary.total_value or 0) if summary is not None else sum(item.value for item in items)
    unknown_value = float(summary.unknown_value or 0) if summary is not None else next(
        (item.value for item in items if item.sector == UNKNOWN_SECTOR_LABEL),
        0.0,
    )
    return SectorExposureOut(
        market=market,
        as_of=target_date,
        basis=basis,
        total_value=total_value,
        coverage=float(summary.coverage or 0) if summary is not None else 0.0,
        unknown_weight=(unknown_value / total_value) if total_value else 0.0,
        items=items,
    )
