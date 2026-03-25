from __future__ import annotations

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.bond_market_quote import BondMarketQuote
from app.models.bond_market_trade import BondMarketTrade
from app.services.cache_utils import item_to_dict
from app.utils.query_params import SortOrder
from etl.fetchers.akshare_reference_client import fetch_bond_market_quote_rows, fetch_bond_market_trade_rows


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


def _ensure_quote_rows(db: Session, refresh: bool) -> None:
    has_rows = db.query(BondMarketQuote.id).first() is not None
    if has_rows and not refresh:
        return
    rows = fetch_bond_market_quote_rows()
    if rows:
        _replace_rows(db, BondMarketQuote, rows)


def _ensure_trade_rows(db: Session, refresh: bool) -> None:
    has_rows = db.query(BondMarketTrade.id).first() is not None
    if has_rows and not refresh:
        return
    rows = fetch_bond_market_trade_rows()
    if rows:
        _replace_rows(db, BondMarketTrade, rows)


def list_bond_market_quotes(
    db: Session,
    *,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: SortOrder = "asc",
    refresh: bool = False,
) -> tuple[list[dict], int]:
    _ensure_quote_rows(db, refresh)
    query = db.query(BondMarketQuote)
    needle = str(keyword or "").strip()
    if needle:
        pattern = f"%{needle}%"
        query = query.filter(or_(BondMarketQuote.bond_name.ilike(pattern), BondMarketQuote.quote_org.ilike(pattern)))
    total = query.count()
    order = BondMarketQuote.bond_name.desc() if sort == "desc" else BondMarketQuote.bond_name.asc()
    items = query.order_by(order, BondMarketQuote.id.asc()).offset(offset).limit(limit).all()
    return [item_to_dict(item) for item in items], total


def list_bond_market_trades(
    db: Session,
    *,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: SortOrder = "asc",
    refresh: bool = False,
) -> tuple[list[dict], int]:
    _ensure_trade_rows(db, refresh)
    query = db.query(BondMarketTrade)
    needle = str(keyword or "").strip()
    if needle:
        pattern = f"%{needle}%"
        query = query.filter(BondMarketTrade.bond_name.ilike(pattern))
    total = query.count()
    order = BondMarketTrade.bond_name.desc() if sort == "desc" else BondMarketTrade.bond_name.asc()
    items = query.order_by(order, BondMarketTrade.id.asc()).offset(offset).limit(limit).all()
    return [item_to_dict(item) for item in items], total
