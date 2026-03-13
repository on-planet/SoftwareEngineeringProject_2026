from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.financials import Financial
from app.schemas.financials import FinancialCreate, FinancialUpdate
from app.utils.query_params import SortOrder


def list_financials(
    db: Session,
    symbol: str,
    limit: int = 50,
    offset: int = 0,
    period: str | None = None,
    min_revenue: float | None = None,
    min_net_income: float | None = None,
    sort: SortOrder = "desc",
):
    """List financial statements by symbol."""
    query = db.query(Financial).filter(Financial.symbol == symbol)
    if period:
        query = query.filter(Financial.period == period)
    if min_revenue is not None:
        query = query.filter(Financial.revenue >= min_revenue)
    if min_net_income is not None:
        query = query.filter(Financial.net_income >= min_net_income)
    total = query.count()
    ordering = Financial.period.asc() if sort == "asc" else Financial.period.desc()
    items = (
        query.order_by(ordering)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return items, total


def create_financial(db: Session, payload: FinancialCreate):
    item = Financial(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_financial(db: Session, symbol: str, period: str, payload: FinancialUpdate):
    item = (
        db.query(Financial)
        .filter(Financial.symbol == symbol, Financial.period == period)
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


def delete_financial(db: Session, symbol: str, period: str) -> bool:
    item = (
        db.query(Financial)
        .filter(Financial.symbol == symbol, Financial.period == period)
        .first()
    )
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
