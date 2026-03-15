from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.financials import Financial
from app.schemas.financials import FinancialCreate, FinancialUpdate
from app.services.live_market_service import get_live_financials


def list_financials(
    symbol: str,
    limit: int = 50,
    offset: int = 0,
    period: str | None = None,
    min_revenue: float | None = None,
    min_net_income: float | None = None,
    sort: str = "desc",
):
    return get_live_financials(
        symbol,
        limit=limit,
        offset=offset,
        period=period,
        min_revenue=min_revenue,
        min_net_income=min_net_income,
        sort=sort,
    )


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
