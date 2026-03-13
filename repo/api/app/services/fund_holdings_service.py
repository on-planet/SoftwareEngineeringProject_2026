from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.fund_holdings import FundHolding
from app.schemas.fund_holdings import FundHoldingCreate, FundHoldingUpdate
from app.utils.query_params import SortOrder


def _resolve_report_date(db: Session, report_date: date | None) -> date | None:
    if report_date is not None:
        return report_date
    latest = db.query(func.max(FundHolding.report_date)).scalar()
    return latest


def list_fund_holdings(
    db: Session,
    fund_code: str | None = None,
    symbol: str | None = None,
    start: date | None = None,
    end: date | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: SortOrder = "desc",
):
    query = db.query(FundHolding)
    if fund_code:
        query = query.filter(FundHolding.fund_code == fund_code)
    if symbol:
        query = query.filter(FundHolding.symbol == symbol)
    if start:
        query = query.filter(FundHolding.report_date >= start)
    if end:
        query = query.filter(FundHolding.report_date <= end)
    total = query.count()
    ordering = FundHolding.report_date.asc() if sort == "asc" else FundHolding.report_date.desc()
    items = query.order_by(ordering).offset(offset).limit(limit).all()
    return items, total


def list_fund_stats(
    db: Session,
    report_date: date | None = None,
):
    target_date = _resolve_report_date(db, report_date)
    if target_date is None:
        return []
    rows = (
        db.query(
            FundHolding.fund_code.label("fund_code"),
            FundHolding.report_date.label("report_date"),
            func.coalesce(func.sum(FundHolding.market_value), 0).label("total_market_value"),
            func.coalesce(func.sum(FundHolding.weight), 0).label("total_weight"),
            func.count(FundHolding.symbol).label("holdings_count"),
        )
        .filter(FundHolding.report_date == target_date)
        .group_by(FundHolding.fund_code, FundHolding.report_date)
        .order_by(FundHolding.fund_code.asc())
        .all()
    )
    return rows


def list_stock_stats(
    db: Session,
    report_date: date | None = None,
):
    target_date = _resolve_report_date(db, report_date)
    if target_date is None:
        return []
    rows = (
        db.query(
            FundHolding.symbol.label("symbol"),
            FundHolding.report_date.label("report_date"),
            func.coalesce(func.sum(FundHolding.market_value), 0).label("total_market_value"),
            func.coalesce(func.sum(FundHolding.weight), 0).label("total_weight"),
            func.count(FundHolding.fund_code).label("fund_count"),
        )
        .filter(FundHolding.report_date == target_date)
        .group_by(FundHolding.symbol, FundHolding.report_date)
        .order_by(FundHolding.symbol.asc())
        .all()
    )
    return rows


def list_fund_series(
    db: Session,
    fund_code: str,
):
    rows = (
        db.query(
            FundHolding.report_date.label("report_date"),
            func.coalesce(func.sum(FundHolding.market_value), 0).label("total_market_value"),
            func.coalesce(func.sum(FundHolding.weight), 0).label("total_weight"),
            func.count(FundHolding.symbol).label("holdings_count"),
        )
        .filter(FundHolding.fund_code == fund_code)
        .group_by(FundHolding.report_date)
        .order_by(FundHolding.report_date.asc())
        .all()
    )
    return rows


def list_stock_series(
    db: Session,
    symbol: str,
):
    rows = (
        db.query(
            FundHolding.report_date.label("report_date"),
            func.coalesce(func.sum(FundHolding.market_value), 0).label("total_market_value"),
            func.coalesce(func.sum(FundHolding.weight), 0).label("total_weight"),
            func.count(FundHolding.fund_code).label("fund_count"),
        )
        .filter(FundHolding.symbol == symbol)
        .group_by(FundHolding.report_date)
        .order_by(FundHolding.report_date.asc())
        .all()
    )
    return rows


def create_fund_holding(db: Session, payload: FundHoldingCreate):
    item = FundHolding(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_fund_holding(db: Session, fund_code: str, symbol: str, report_date: date, payload: FundHoldingUpdate):
    item = (
        db.query(FundHolding)
        .filter(
            FundHolding.fund_code == fund_code,
            FundHolding.symbol == symbol,
            FundHolding.report_date == report_date,
        )
        .first()
    )
    if item is None:
        return None
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_fund_holding(db: Session, fund_code: str, symbol: str, report_date: date) -> bool:
    item = (
        db.query(FundHolding)
        .filter(
            FundHolding.fund_code == fund_code,
            FundHolding.symbol == symbol,
            FundHolding.report_date == report_date,
        )
        .first()
    )
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
