from __future__ import annotations

from datetime import date
import json

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.stock_institute_hold import StockInstituteHold, StockInstituteHoldDetail
from app.models.stock_institute_recommend import StockInstituteRecommend, StockInstituteRecommendDetail
from app.services.cache_utils import item_to_dict
from app.utils.query_params import SortOrder
from app.utils.symbols import normalize_symbol
from etl.fetchers.akshare_reference_client import (
    fetch_stock_institute_hold_detail_rows,
    fetch_stock_institute_hold_rows,
    fetch_stock_institute_recommend_detail_rows,
    fetch_stock_institute_recommend_rows,
)


def _parse_payload(raw_json: str | None) -> dict | None:
    if not raw_json:
        return None
    try:
        payload = json.loads(raw_json)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _quarter_candidates(anchor: date | None = None, count: int = 8) -> list[str]:
    today = anchor or date.today()
    quarter = ((today.month - 1) // 3) + 1
    year = today.year
    output: list[str] = []
    current_year = year
    current_quarter = quarter
    for _ in range(count):
        output.append(f"{current_year}{current_quarter}")
        current_quarter -= 1
        if current_quarter <= 0:
            current_quarter = 4
            current_year -= 1
    return output


def _replace_partition(db: Session, query, model, rows: list[dict]) -> int:
    if not rows:
        return 0
    try:
        query.delete(synchronize_session=False)
        db.add_all(model(**row) for row in rows)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return len(rows)


def _ensure_hold_rows(db: Session, quarter: str | None, refresh: bool) -> str | None:
    target_quarter = str(quarter or "").strip() or None
    if target_quarter is None:
        target_quarter = db.query(func.max(StockInstituteHold.quarter)).scalar()
    existing_query = db.query(StockInstituteHold)
    if target_quarter:
        existing_query = existing_query.filter(StockInstituteHold.quarter == target_quarter)
    if target_quarter and existing_query.first() is not None and not refresh:
        return target_quarter
    candidates = [target_quarter] if target_quarter else _quarter_candidates()
    for candidate in candidates:
        if not candidate:
            continue
        rows = fetch_stock_institute_hold_rows(candidate)
        if rows:
            _replace_partition(
                db,
                db.query(StockInstituteHold).filter(StockInstituteHold.quarter == candidate),
                StockInstituteHold,
                rows,
            )
            return candidate
    return target_quarter


def _ensure_hold_detail_rows(db: Session, symbol: str, quarter: str | None, refresh: bool) -> str | None:
    normalized = normalize_symbol(symbol)
    target_quarter = str(quarter or "").strip() or None
    if target_quarter is None:
        target_quarter = (
            db.query(func.max(StockInstituteHoldDetail.quarter))
            .filter(StockInstituteHoldDetail.stock_symbol == normalized)
            .scalar()
        )
    existing_query = db.query(StockInstituteHoldDetail).filter(
        StockInstituteHoldDetail.stock_symbol == normalized,
    )
    if target_quarter:
        existing_query = existing_query.filter(StockInstituteHoldDetail.quarter == target_quarter)
    if target_quarter and existing_query.first() is not None and not refresh:
        return target_quarter
    candidates = [target_quarter] if target_quarter else _quarter_candidates()
    for candidate in candidates:
        if not candidate:
            continue
        rows = fetch_stock_institute_hold_detail_rows(normalized, candidate)
        if rows:
            _replace_partition(
                db,
                db.query(StockInstituteHoldDetail).filter(
                    StockInstituteHoldDetail.stock_symbol == normalized,
                    StockInstituteHoldDetail.quarter == candidate,
                ),
                StockInstituteHoldDetail,
                rows,
            )
            return candidate
    return target_quarter


def _ensure_recommend_rows(db: Session, category: str, refresh: bool) -> None:
    existing = db.query(StockInstituteRecommend.id).filter(StockInstituteRecommend.category == category).first()
    if existing is not None and not refresh:
        return
    rows = fetch_stock_institute_recommend_rows(category)
    if rows:
        _replace_partition(
            db,
            db.query(StockInstituteRecommend).filter(StockInstituteRecommend.category == category),
            StockInstituteRecommend,
            rows,
        )


def _ensure_recommend_detail_rows(db: Session, symbol: str, refresh: bool) -> str:
    normalized = normalize_symbol(symbol)
    existing = db.query(StockInstituteRecommendDetail.id).filter(StockInstituteRecommendDetail.symbol == normalized).first()
    if existing is not None and not refresh:
        return normalized
    rows = fetch_stock_institute_recommend_detail_rows(normalized)
    if rows:
        _replace_partition(
            db,
            db.query(StockInstituteRecommendDetail).filter(StockInstituteRecommendDetail.symbol == normalized),
            StockInstituteRecommendDetail,
            rows,
        )
    return normalized


def list_stock_institute_holds(
    db: Session,
    *,
    quarter: str | None = None,
    symbol: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: SortOrder = "desc",
    refresh: bool = False,
) -> tuple[list[dict], int, str | None]:
    target_quarter = _ensure_hold_rows(db, quarter, refresh)
    query = db.query(StockInstituteHold)
    if target_quarter:
        query = query.filter(StockInstituteHold.quarter == target_quarter)
    if symbol:
        query = query.filter(StockInstituteHold.symbol == normalize_symbol(symbol))
    needle = str(keyword or "").strip()
    if needle:
        pattern = f"%{needle}%"
        query = query.filter(or_(StockInstituteHold.symbol.ilike(pattern), StockInstituteHold.stock_name.ilike(pattern)))
    total = query.count()
    order = StockInstituteHold.institute_count.desc() if sort == "desc" else StockInstituteHold.institute_count.asc()
    items = query.order_by(order, StockInstituteHold.symbol.asc()).offset(offset).limit(limit).all()
    return [item_to_dict(item) for item in items], total, target_quarter


def list_stock_institute_hold_details(
    db: Session,
    *,
    symbol: str,
    quarter: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: SortOrder = "desc",
    refresh: bool = False,
) -> tuple[list[dict], int, str | None]:
    normalized = normalize_symbol(symbol)
    target_quarter = _ensure_hold_detail_rows(db, normalized, quarter, refresh)
    query = db.query(StockInstituteHoldDetail).filter(StockInstituteHoldDetail.stock_symbol == normalized)
    if target_quarter:
        query = query.filter(StockInstituteHoldDetail.quarter == target_quarter)
    total = query.count()
    order = StockInstituteHoldDetail.shares.desc() if sort == "desc" else StockInstituteHoldDetail.shares.asc()
    rows = query.order_by(order, StockInstituteHoldDetail.id.asc()).offset(offset).limit(limit).all()
    items: list[dict] = []
    for row in rows:
        payload = item_to_dict(row)
        payload["payload"] = _parse_payload(row.raw_json)
        items.append(payload)
    return items, total, target_quarter


def list_stock_institute_recommendations(
    db: Session,
    *,
    category: str = "投资评级选股",
    symbol: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: SortOrder = "desc",
    refresh: bool = False,
) -> tuple[list[dict], int]:
    _ensure_recommend_rows(db, category, refresh)
    query = db.query(StockInstituteRecommend).filter(StockInstituteRecommend.category == category)
    if symbol:
        query = query.filter(StockInstituteRecommend.symbol == normalize_symbol(symbol))
    needle = str(keyword or "").strip()
    if needle:
        pattern = f"%{needle}%"
        query = query.filter(or_(StockInstituteRecommend.symbol.ilike(pattern), StockInstituteRecommend.stock_name.ilike(pattern)))
    total = query.count()
    order = StockInstituteRecommend.rating_date.desc() if sort == "desc" else StockInstituteRecommend.rating_date.asc()
    rows = query.order_by(order, StockInstituteRecommend.id.asc()).offset(offset).limit(limit).all()
    items: list[dict] = []
    for row in rows:
        payload = item_to_dict(row)
        payload["payload"] = _parse_payload(row.raw_json)
        items.append(payload)
    return items, total


def list_stock_institute_recommendation_details(
    db: Session,
    *,
    symbol: str,
    limit: int = 50,
    offset: int = 0,
    sort: SortOrder = "desc",
    refresh: bool = False,
) -> tuple[list[dict], int]:
    normalized = _ensure_recommend_detail_rows(db, symbol, refresh)
    query = db.query(StockInstituteRecommendDetail).filter(StockInstituteRecommendDetail.symbol == normalized)
    total = query.count()
    order = StockInstituteRecommendDetail.rating_date.desc() if sort == "desc" else StockInstituteRecommendDetail.rating_date.asc()
    rows = query.order_by(order, StockInstituteRecommendDetail.id.asc()).offset(offset).limit(limit).all()
    items: list[dict] = []
    for row in rows:
        payload = item_to_dict(row)
        payload["payload"] = _parse_payload(row.raw_json)
        items.append(payload)
    return items, total
