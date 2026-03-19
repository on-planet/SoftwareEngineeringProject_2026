from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.cache import get_json
from app.models.daily_prices import DailyPrice
from app.models.sector_exposure import SectorExposure
from app.models.sector_exposure_summary import SectorExposureSummary
from app.models.stocks import Stock
from app.schemas.sector_exposure import SectorExposureItemOut, SectorExposureOut

DEFAULT_SECTOR_EXPOSURE_BASIS = "market_value"
UNKNOWN_SECTOR_LABEL = "未分类"
UNKNOWN_SECTOR_INPUTS = {
    "",
    "unknown",
    "未知",
    "未分类",
    "n/a",
    "na",
    "none",
    "null",
}


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


def _normalize_sector_label(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return UNKNOWN_SECTOR_LABEL
    if text.lower() in UNKNOWN_SECTOR_INPUTS:
        return UNKNOWN_SECTOR_LABEL
    return text


def _latest_daily_date_by_market(db: Session, market: str) -> date | None:
    return (
        db.query(func.max(DailyPrice.date))
        .join(Stock, Stock.symbol == DailyPrice.symbol)
        .filter(Stock.market == market)
        .scalar()
    )


def _build_market_proxy_exposure(
    db: Session,
    market: str,
    as_of: date,
) -> dict:
    total_symbols = (
        db.query(func.count(Stock.symbol))
        .filter(Stock.market == market)
        .scalar()
        or 0
    )
    if total_symbols <= 0:
        return {
            "items": [],
            "total_value": 0.0,
            "coverage": 0.0,
            "total_symbol_count": 0,
            "covered_symbol_count": 0,
            "classified_symbol_count": 0,
            "unknown_symbol_count": 0,
            "unknown_value": 0.0,
        }

    covered_symbols = (
        db.query(func.count(Stock.symbol))
        .join(DailyPrice, DailyPrice.symbol == Stock.symbol)
        .filter(
            Stock.market == market,
            DailyPrice.date == as_of,
            DailyPrice.close.isnot(None),
            DailyPrice.close > 0,
        )
        .scalar()
        or 0
    )
    classified_symbols = (
        db.query(func.count(Stock.symbol))
        .filter(
            Stock.market == market,
            Stock.sector.isnot(None),
            func.lower(func.trim(Stock.sector)).notin_(tuple(UNKNOWN_SECTOR_INPUTS)),
        )
        .scalar()
        or 0
    )
    unknown_symbol_count = max(0, int(total_symbols) - int(classified_symbols))

    grouped_rows = (
        db.query(
            Stock.sector.label("sector"),
            func.sum(DailyPrice.close).label("value"),
            func.count(Stock.symbol).label("symbol_count"),
        )
        .join(DailyPrice, DailyPrice.symbol == Stock.symbol)
        .filter(
            Stock.market == market,
            DailyPrice.date == as_of,
            DailyPrice.close.isnot(None),
            DailyPrice.close > 0,
        )
        .group_by(Stock.sector)
        .all()
    )

    items: list[SectorExposureItemOut] = []
    total_value = 0.0
    for row in grouped_rows:
        value = float(row.value or 0.0)
        if value <= 0:
            continue
        total_value += value
        items.append(
            SectorExposureItemOut(
                sector=_normalize_sector_label(row.sector),
                value=value,
                weight=0.0,
                symbol_count=int(row.symbol_count or 0),
            )
        )

    if total_value > 0:
        for item in items:
            item.weight = item.value / total_value
    items.sort(key=lambda item: item.value, reverse=True)

    unknown_value = next((item.value for item in items if item.sector == UNKNOWN_SECTOR_LABEL), 0.0)
    return {
        "items": items,
        "total_value": total_value,
        "coverage": (float(covered_symbols) / float(total_symbols)) if total_symbols else 0.0,
        "total_symbol_count": int(total_symbols),
        "covered_symbol_count": int(covered_symbols),
        "classified_symbol_count": int(classified_symbols),
        "unknown_symbol_count": int(unknown_symbol_count),
        "unknown_value": float(unknown_value),
    }


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

    if target_date is None and market:
        proxy_date = _latest_daily_date_by_market(db, target_market)
        if proxy_date is not None:
            proxy_payload = _build_market_proxy_exposure(db, target_market, proxy_date)
            proxy_items = proxy_payload["items"]
            proxy_items.sort(key=lambda item: item.weight, reverse=(sort == "desc"))
            if offset:
                proxy_items = proxy_items[offset:]
            if limit is not None:
                proxy_items = proxy_items[:limit]
            total_value = float(proxy_payload["total_value"])
            unknown_value = float(proxy_payload["unknown_value"])
            return SectorExposureOut(
                market=market,
                as_of=proxy_date,
                basis=f"{basis}_proxy_close",
                total_value=total_value,
                coverage=float(proxy_payload["coverage"]),
                unknown_weight=(unknown_value / total_value) if total_value else 0.0,
                items=proxy_items,
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

    if market and not items:
        proxy_payload = _build_market_proxy_exposure(db, target_market, target_date)
        proxy_items = proxy_payload["items"]
        proxy_items.sort(key=lambda item: item.weight, reverse=(sort == "desc"))
        if offset:
            proxy_items = proxy_items[offset:]
        if limit is not None:
            proxy_items = proxy_items[:limit]
        total_value = float(proxy_payload["total_value"])
        unknown_value = float(proxy_payload["unknown_value"])
        if proxy_items or total_value > 0:
            return SectorExposureOut(
                market=market,
                as_of=target_date,
                basis=f"{basis}_proxy_close",
                total_value=total_value,
                coverage=float(proxy_payload["coverage"]),
                unknown_weight=(unknown_value / total_value) if total_value else 0.0,
                items=proxy_items,
            )

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
