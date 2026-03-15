from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.services.live_index_service import list_live_index_constituents


def list_index_constituents(
    db: Session,
    index_symbol: str,
    as_of: date | None = None,
    limit: int = 200,
    offset: int = 0,
):
    del db
    return list_live_index_constituents(index_symbol, as_of=as_of, limit=limit, offset=offset)
