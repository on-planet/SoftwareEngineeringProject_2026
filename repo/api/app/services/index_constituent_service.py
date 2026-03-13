from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.index_constituent import IndexConstituent


def list_index_constituents(
    db: Session,
    index_symbol: str,
    as_of: date | None = None,
    limit: int = 200,
    offset: int = 0,
):
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
    return items, total
