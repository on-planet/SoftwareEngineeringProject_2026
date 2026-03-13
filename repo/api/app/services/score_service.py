from __future__ import annotations

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.models.fundamental_score import FundamentalScore
from app.schemas.fundamental import FundamentalCreate, FundamentalUpdate


def get_fundamental_score(db: Session, symbol: str):
    """Get fundamental score for a symbol."""
    return (
        db.query(FundamentalScore)
        .filter(FundamentalScore.symbol == symbol)
        .order_by(desc(FundamentalScore.updated_at))
        .first()
    )


def create_fundamental_score(db: Session, payload: FundamentalCreate):
    item = FundamentalScore(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_fundamental_score(db: Session, symbol: str, payload: FundamentalUpdate):
    item = db.query(FundamentalScore).filter(FundamentalScore.symbol == symbol).first()
    if item is None:
        return None
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_fundamental_score(db: Session, symbol: str) -> bool:
    item = db.query(FundamentalScore).filter(FundamentalScore.symbol == symbol).first()
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
