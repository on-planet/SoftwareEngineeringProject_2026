from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.stock_live_snapshot import StockLiveSnapshot
from app.models.stocks import Stock
from app.schemas.stock import StockCreate, StockUpdate
from app.services.profile_service import (
    get_stock_overview_payload,
    get_stock_profile_extras_payload,
    get_stock_profile_payload,
)
from app.services.live_market_service import (
    get_live_stock_daily,
    list_live_stocks,
)


def list_stocks(
    *,
    market: str | None = None,
    keyword: str | None = None,
    sector: str | None = None,
    limit: int = 100,
    offset: int = 0,
    sort: str = "asc",
):
    return list_live_stocks(
        market=market,
        keyword=keyword,
        sector=sector,
        limit=limit,
        offset=offset,
        sort=sort,
    )


def get_stock_profile(symbol: str, *, prefer_live: bool = False):
    return get_stock_profile_payload(symbol, prefer_live=prefer_live)


def get_stock_overview_profile(symbol: str, *, prefer_live: bool = False):
    return get_stock_overview_payload(symbol, prefer_live=prefer_live)


def get_stock_profile_extras(symbol: str, *, prefer_live: bool = False):
    return get_stock_profile_extras_payload(symbol, prefer_live=prefer_live)


def get_stock_daily(
    symbol: str,
    start: date | None = None,
    end: date | None = None,
    sort: str = "asc",
    min_volume: float | None = None,
):
    return get_live_stock_daily(symbol, start=start, end=end, sort=sort, min_volume=min_volume)


def create_stock(db: Session, payload: StockCreate):
    item = Stock(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_stock(db: Session, symbol: str, payload: StockUpdate):
    item = db.query(Stock).filter(Stock.symbol == symbol).first()
    if item is None:
        return None
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_stock(db: Session, symbol: str) -> bool:
    item = db.query(Stock).filter(Stock.symbol == symbol).first()
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True


def _normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def _normalize_symbols(symbols: list[str]) -> list[str]:
    unique = set()
    result: list[str] = []
    for raw in symbols:
        symbol = _normalize_symbol(raw)
        if not symbol or symbol in unique:
            continue
        unique.add(symbol)
        result.append(symbol)
        if len(result) >= 200:
            break
    return result


def _build_quote_payload(snapshot: StockLiveSnapshot | None) -> dict | None:
    if snapshot is None:
        return None
    payload = {
        "current": snapshot.current,
        "change": snapshot.change,
        "percent": snapshot.percent,
        "open": snapshot.open,
        "high": snapshot.high,
        "low": snapshot.low,
        "last_close": snapshot.last_close,
        "volume": snapshot.volume,
        "amount": snapshot.amount,
        "turnover_rate": snapshot.turnover_rate,
        "amplitude": snapshot.amplitude,
        "timestamp": snapshot.quote_timestamp,
    }
    return payload if any(value is not None for value in payload.values()) else None


def get_stock_compare_batch(db: Session, symbols: list[str], *, prefer_live: bool = False) -> list[dict]:
    normalized_symbols = _normalize_symbols(symbols)
    if not normalized_symbols:
        return []

    rows = (
        db.query(Stock, StockLiveSnapshot)
        .outerjoin(StockLiveSnapshot, StockLiveSnapshot.symbol == Stock.symbol)
        .filter(Stock.symbol.in_(normalized_symbols))
        .all()
    )
    row_map = {
        _normalize_symbol(stock.symbol): (stock, snapshot)
        for stock, snapshot in rows
        if stock is not None and stock.symbol
    }

    items: list[dict] = []
    for symbol in normalized_symbols:
        stock_row = row_map.get(symbol)
        if stock_row is not None:
            stock, snapshot = stock_row
            quote = _build_quote_payload(snapshot)
            if prefer_live and quote is None:
                profile = get_stock_overview_payload(symbol, prefer_live=True)
                if profile:
                    items.append(
                        {
                            "symbol": _normalize_symbol(str(profile.get("symbol") or symbol)),
                            "name": str(profile.get("name") or stock.name or symbol),
                            "market": str(profile.get("market") or stock.market or ""),
                            "sector": str(profile.get("sector") or stock.sector or ""),
                            "quote": profile.get("quote"),
                            "error": None,
                        }
                    )
                    continue
            items.append(
                {
                    "symbol": _normalize_symbol(stock.symbol),
                    "name": str(stock.name or symbol),
                    "market": str(stock.market or ""),
                    "sector": str(stock.sector or ""),
                    "quote": quote,
                    "error": None,
                }
            )
            continue

        profile = get_stock_overview_payload(symbol, prefer_live=prefer_live)
        if profile:
            items.append(
                {
                    "symbol": _normalize_symbol(str(profile.get("symbol") or symbol)),
                    "name": str(profile.get("name") or symbol),
                    "market": str(profile.get("market") or ""),
                    "sector": str(profile.get("sector") or ""),
                    "quote": profile.get("quote"),
                    "error": None,
                }
            )
        else:
            items.append(
                {
                    "symbol": symbol,
                    "name": symbol,
                    "market": "",
                    "sector": "",
                    "quote": None,
                    "error": "Stock not found",
                }
            )
    return items
