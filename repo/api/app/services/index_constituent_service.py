from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.index_constituent import IndexConstituent
from app.services.cache_utils import build_cache_key, items_to_dicts

INDEX_CONSTITUENT_CACHE_TTL = 1800


def list_index_constituents(
    db: Session,
    index_symbol: str,
    as_of: date | None = None,
    limit: int = 200,
    offset: int = 0,
):
    cache_key = build_cache_key(
        "index:constituents",
        index_symbol=index_symbol,
        as_of=as_of,
        limit=limit,
        offset=offset,
    )
    cached = get_json(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("items"), list) and isinstance(cached.get("total"), int):
        return cached["items"], cached["total"]

    query = db.query(IndexConstituent).filter(IndexConstituent.index_symbol == index_symbol)
    if as_of is not None:
        query = query.filter(IndexConstituent.date == as_of)
    items = (
        query.order_by(IndexConstituent.weight.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    total = query.count()
    set_json(cache_key, {"items": items_to_dicts(items), "total": total}, ttl=INDEX_CONSTITUENT_CACHE_TTL)
    return items, total
