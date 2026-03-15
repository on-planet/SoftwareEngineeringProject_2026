from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.indices import Index
from app.schemas.index import IndexCreate, IndexUpdate
from app.services.live_index_service import list_live_indices


def list_indices(db: Session, as_of: date | None = None, sort: str = "desc"):
    del db
    return list_live_indices(as_of=as_of, sort=sort)


def create_index(db: Session, payload: IndexCreate):
    item = Index(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_index(db: Session, symbol: str, index_date: date, payload: IndexUpdate):
    item = db.query(Index).filter(Index.symbol == symbol, Index.date == index_date).first()
    if item is None:
        return None
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_index(db: Session, symbol: str, index_date: date) -> bool:
    item = db.query(Index).filter(Index.symbol == symbol, Index.date == index_date).first()
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
