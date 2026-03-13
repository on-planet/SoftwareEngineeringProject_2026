from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.user_portfolio import UserPortfolio
from app.schemas.user import PortfolioCreate, PortfolioUpdate, PortfolioBatchItem


def get_user_portfolio(
    db: Session,
    user_id: int,
    symbol: str | None = None,
    min_shares: float | None = None,
    max_shares: float | None = None,
    limit: int = 200,
    offset: int = 0,
):
    """Get user portfolio holdings."""
    query = db.query(UserPortfolio).filter(UserPortfolio.user_id == user_id)
    if symbol:
        query = query.filter(UserPortfolio.symbol == symbol)
    if min_shares is not None:
        query = query.filter(UserPortfolio.shares >= min_shares)
    if max_shares is not None:
        query = query.filter(UserPortfolio.shares <= max_shares)
    total = query.count()
    items = (
        query.order_by(UserPortfolio.symbol.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return items, total


def create_portfolio(db: Session, payload: PortfolioCreate):
    item = UserPortfolio(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def batch_upsert_portfolio(db: Session, user_id: int, items: list[PortfolioBatchItem]) -> list[UserPortfolio]:
    results: list[UserPortfolio] = []
    if not items:
        return results
    symbol_map = {item.symbol: item for item in items if item.symbol}
    if not symbol_map:
        return results
    existing = (
        db.query(UserPortfolio)
        .filter(UserPortfolio.user_id == user_id, UserPortfolio.symbol.in_(list(symbol_map.keys())))
        .all()
    )
    existing_map = {item.symbol: item for item in existing}
    for symbol, payload in symbol_map.items():
        current = existing_map.get(symbol)
        if current is None:
            current = UserPortfolio(user_id=user_id, symbol=symbol, avg_cost=payload.avg_cost, shares=payload.shares)
            db.add(current)
        else:
            current.avg_cost = payload.avg_cost
            current.shares = payload.shares
        results.append(current)
    db.commit()
    for item in results:
        db.refresh(item)
    return results


def update_portfolio(db: Session, user_id: int, symbol: str, payload: PortfolioUpdate):
    item = (
        db.query(UserPortfolio)
        .filter(UserPortfolio.user_id == user_id, UserPortfolio.symbol == symbol)
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


def delete_portfolio(db: Session, user_id: int, symbol: str) -> bool:
    item = (
        db.query(UserPortfolio)
        .filter(UserPortfolio.user_id == user_id, UserPortfolio.symbol == symbol)
        .first()
    )
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
