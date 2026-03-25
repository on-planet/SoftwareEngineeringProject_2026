from __future__ import annotations

from datetime import date
import json

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.stock_report_disclosure import StockReportDisclosure
from app.services.cache_utils import item_to_dict
from app.utils.query_params import SortOrder
from app.utils.symbols import normalize_symbol
from etl.fetchers.akshare_reference_client import fetch_stock_report_disclosure_rows


def _parse_payload(raw_json: str | None) -> dict | None:
    if not raw_json:
        return None
    try:
        payload = json.loads(raw_json)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _period_candidates(anchor: date | None = None) -> list[str]:
    today = anchor or date.today()
    year = today.year
    return [
        f"{year - 1}年报",
        f"{year}一季",
        f"{year}半年报",
        f"{year}三季",
        f"{year}年报",
        f"{year - 2}年报",
    ]


def _replace_partition(db: Session, market: str, period: str, rows: list[dict]) -> int:
    if not rows:
        return 0
    try:
        db.query(StockReportDisclosure).filter(
            StockReportDisclosure.market == market,
            StockReportDisclosure.period == period,
        ).delete(synchronize_session=False)
        db.add_all(StockReportDisclosure(**row) for row in rows)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return len(rows)


def _ensure_rows(db: Session, market: str, period: str | None, refresh: bool) -> str | None:
    target_period = str(period or "").strip() or None
    if target_period is None:
        latest_row = (
            db.query(StockReportDisclosure.period)
            .filter(StockReportDisclosure.market == market)
            .order_by(StockReportDisclosure.as_of.desc(), StockReportDisclosure.id.desc())
            .first()
        )
        target_period = str(latest_row[0]) if latest_row and latest_row[0] else None
    existing = db.query(StockReportDisclosure.id).filter(StockReportDisclosure.market == market)
    if target_period:
        existing = existing.filter(StockReportDisclosure.period == target_period)
    if target_period and existing.first() is not None and not refresh:
        return target_period
    candidates = [target_period] if target_period else _period_candidates()
    for candidate in candidates:
        if not candidate:
            continue
        rows = fetch_stock_report_disclosure_rows(market, candidate)
        if rows:
            _replace_partition(db, market, candidate, rows)
            return candidate
    return target_period


def list_stock_report_disclosures(
    db: Session,
    *,
    market: str = "沪深京",
    period: str | None = None,
    symbol: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: SortOrder = "asc",
    refresh: bool = False,
) -> tuple[list[dict], int, str | None]:
    target_period = _ensure_rows(db, market, period, refresh)
    query = db.query(StockReportDisclosure).filter(StockReportDisclosure.market == market)
    if target_period:
        query = query.filter(StockReportDisclosure.period == target_period)
    if symbol:
        query = query.filter(StockReportDisclosure.symbol == normalize_symbol(symbol))
    needle = str(keyword or "").strip()
    if needle:
        pattern = f"%{needle}%"
        query = query.filter(or_(StockReportDisclosure.symbol.ilike(pattern), StockReportDisclosure.stock_name.ilike(pattern)))
    total = query.count()
    order = StockReportDisclosure.first_booking.desc() if sort == "desc" else StockReportDisclosure.first_booking.asc()
    rows = query.order_by(order, StockReportDisclosure.symbol.asc()).offset(offset).limit(limit).all()
    items: list[dict] = []
    for row in rows:
        payload = item_to_dict(row)
        payload["payload"] = _parse_payload(row.raw_json)
        items.append(payload)
    return items, total, target_period
