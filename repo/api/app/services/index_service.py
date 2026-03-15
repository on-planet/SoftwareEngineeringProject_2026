from __future__ import annotations

from datetime import date
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.indices import Index
from app.services.cache_utils import build_cache_key, items_to_dicts
from app.schemas.index import IndexCreate, IndexUpdate
from app.utils.query_params import SortOrder

INDEX_CACHE_TTL = 900


def list_indices(db: Session, as_of: date | None = None, sort: SortOrder = "desc"):
    """List indices by date (default latest)."""
    cache_key = build_cache_key("index:list", as_of=as_of, sort=sort)
    cached = get_json(cache_key)
    if isinstance(cached, list):
        return cached

    target_date = as_of
    if target_date is None:
        target_date = db.query(func.max(Index.date)).scalar()
    if target_date is None:
        return []
    query = db.query(Index).filter(Index.date == target_date)
    if sort == "asc":
        items = query.order_by(Index.symbol.asc()).all()
    else:
        items = query.order_by(Index.symbol.desc()).all()
    set_json(cache_key, items_to_dicts(items), ttl=INDEX_CACHE_TTL)
    return items


def create_index(db: Session, payload: IndexCreate):
    item = Index(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_index(db: Session, symbol: str, index_date: date, payload: IndexUpdate):
    item = (
        db.query(Index)
        .filter(Index.symbol == symbol, Index.date == index_date)
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


def delete_index(db: Session, symbol: str, index_date: date) -> bool:
    item = (
        db.query(Index)
        .filter(Index.symbol == symbol, Index.date == index_date)
        .first()
    )
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
