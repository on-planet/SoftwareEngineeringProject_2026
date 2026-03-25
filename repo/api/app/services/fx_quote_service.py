from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.fx_quote import FxPairQuote, FxSpotQuote, FxSwapQuote
from app.services.cache_utils import item_to_dict
from app.utils.query_params import SortOrder
from etl.fetchers.akshare_reference_client import (
    fetch_fx_pair_quote_rows,
    fetch_fx_spot_quote_rows,
    fetch_fx_swap_quote_rows,
)


def _replace_rows(db: Session, model, rows: list[dict]) -> int:
    if not rows:
        return 0
    try:
        db.query(model).delete()
        db.add_all(model(**row) for row in rows)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return len(rows)


def _ensure_rows(db: Session, model, refresh: bool, fetcher) -> None:
    has_rows = db.query(model.id).first() is not None
    if has_rows and not refresh:
        return
    rows = fetcher()
    if rows:
        _replace_rows(db, model, rows)


def _list_rows(db: Session, model, *, pair: str | None, limit: int, offset: int, sort: SortOrder) -> tuple[list[dict], int]:
    query = db.query(model)
    needle = str(pair or "").strip().upper()
    if needle:
        query = query.filter(model.currency_pair == needle)
    total = query.count()
    order = model.currency_pair.desc() if sort == "desc" else model.currency_pair.asc()
    items = query.order_by(order, model.id.asc()).offset(offset).limit(limit).all()
    return [item_to_dict(item) for item in items], total


def list_fx_spot_quotes(
    db: Session,
    *,
    pair: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: SortOrder = "asc",
    refresh: bool = False,
) -> tuple[list[dict], int]:
    _ensure_rows(db, FxSpotQuote, refresh, fetch_fx_spot_quote_rows)
    return _list_rows(db, FxSpotQuote, pair=pair, limit=limit, offset=offset, sort=sort)


def list_fx_swap_quotes(
    db: Session,
    *,
    pair: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: SortOrder = "asc",
    refresh: bool = False,
) -> tuple[list[dict], int]:
    _ensure_rows(db, FxSwapQuote, refresh, fetch_fx_swap_quote_rows)
    return _list_rows(db, FxSwapQuote, pair=pair, limit=limit, offset=offset, sort=sort)


def list_fx_pair_quotes(
    db: Session,
    *,
    pair: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: SortOrder = "asc",
    refresh: bool = False,
) -> tuple[list[dict], int]:
    _ensure_rows(db, FxPairQuote, refresh, fetch_fx_pair_quote_rows)
    return _list_rows(db, FxPairQuote, pair=pair, limit=limit, offset=offset, sort=sort)
