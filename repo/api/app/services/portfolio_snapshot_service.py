from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.daily_prices import DailyPrice
from app.models.stocks import Stock
from app.models.user_bought_target import UserBoughtTarget
from app.models.user_watch_target import UserWatchTarget
from etl.utils.sector_taxonomy import normalize_sector_name

WATCH_TARGET_NOTIONAL_UNIT = 100.0


@dataclass(frozen=True)
class HoldingSnapshot:
    symbol: str
    name: str
    market: str
    raw_sector: str
    sector: str
    buy_price: float
    lots: float
    fee: float
    buy_date: date
    cost_value: float
    current_price: float
    current_value: float
    pnl_value: float
    pnl_pct: float
    weight: float


def canonical_sector_label(raw_sector: str | None, market: str | None) -> str:
    normalized = normalize_sector_name(raw_sector, market=market)
    lowered = str(raw_sector or "").strip().lower()
    if normalized and normalized != str(raw_sector or "").strip():
        return normalized
    if any(keyword in lowered for keyword in ("bank", "insurance", "broker", "finance", "fintech")):
        return "金融"
    if any(
        keyword in lowered
        for keyword in ("tech", "technology", "software", "semiconductor", "internet", "cloud", "ai")
    ):
        return "科技"
    if any(keyword in lowered for keyword in ("media", "telecom", "gaming", "entertainment")):
        return "电信传媒"
    if any(keyword in lowered for keyword in ("real estate", "property", "reit")):
        return "房地产"
    if any(keyword in lowered for keyword in ("utility", "utilities", "power", "water", "gas")):
        return "公用事业"
    if any(keyword in lowered for keyword in ("health", "healthcare", "biotech", "pharma", "medical")):
        return "医疗健康"
    if any(keyword in lowered for keyword in ("consumer", "retail", "food", "beverage", "ecommerce", "e-commerce")):
        return "消费"
    if any(keyword in lowered for keyword in ("energy", "oil", "gas", "coal", "petro")):
        return "能源"
    if any(keyword in lowered for keyword in ("chemical", "material", "steel", "metal", "mining")):
        return "原材料"
    if any(keyword in lowered for keyword in ("airline", "aviation", "airport", "travel", "tourism", "hotel")):
        return "航空旅游"
    if any(keyword in lowered for keyword in ("transport", "shipping", "logistics", "rail", "port")):
        return "交通运输"
    if any(keyword in lowered for keyword in ("industrial", "machinery", "equipment", "manufacturing")):
        return "工业制造"
    if any(keyword in lowered for keyword in ("appliance", "home", "furniture")):
        return "家居家电"
    return normalized or str(raw_sector or "").strip() or "未分类"


def sector_has_keyword(snapshot: HoldingSnapshot, keywords: tuple[str, ...]) -> bool:
    raw = snapshot.raw_sector.lower()
    sector = snapshot.sector.lower()
    return any(keyword in raw or keyword in sector for keyword in keywords)


def latest_price_map(db: Session, symbols: list[str]) -> tuple[dict[str, float], date | None]:
    if not symbols:
        return {}, None
    subquery = (
        db.query(DailyPrice.symbol, func.max(DailyPrice.date).label("latest_date"))
        .filter(DailyPrice.symbol.in_(symbols))
        .group_by(DailyPrice.symbol)
        .subquery()
    )
    rows = (
        db.query(DailyPrice.symbol, DailyPrice.close, DailyPrice.date)
        .join(
            subquery,
            (DailyPrice.symbol == subquery.c.symbol) & (DailyPrice.date == subquery.c.latest_date),
        )
        .all()
    )
    price_map = {str(symbol): float(close or 0.0) for symbol, close, _ in rows}
    latest_dates = [item_date for _, _, item_date in rows if isinstance(item_date, date)]
    return price_map, (max(latest_dates) if latest_dates else None)


def build_stock_snapshot_map(db: Session, symbols: list[str]) -> dict[str, dict[str, str]]:
    if not symbols:
        return {}
    stock_rows = (
        db.query(Stock.symbol, Stock.name, Stock.market, Stock.sector)
        .filter(Stock.symbol.in_(symbols))
        .all()
    )
    return {
        str(symbol): {
            "name": str(name or symbol),
            "market": str(market or ""),
            "raw_sector": str(sector or ""),
            "sector": canonical_sector_label(sector, market),
        }
        for symbol, name, market, sector in stock_rows
    }


def load_bought_target_snapshots(db: Session, user_id: int) -> tuple[list[HoldingSnapshot], float, float, date | None]:
    holdings = (
        db.query(UserBoughtTarget)
        .filter(UserBoughtTarget.user_id == user_id)
        .order_by(UserBoughtTarget.updated_at.desc(), UserBoughtTarget.symbol.asc())
        .all()
    )
    symbols = [str(item.symbol) for item in holdings]
    if not symbols:
        return [], 0.0, 0.0, None

    price_map, as_of = latest_price_map(db, symbols)
    stock_map = build_stock_snapshot_map(db, symbols)

    total_value = 0.0
    total_cost = 0.0
    rows: list[dict[str, object]] = []
    for item in holdings:
        symbol = str(item.symbol)
        stock_payload = stock_map.get(symbol, {})
        buy_price = float(item.buy_price or 0.0)
        lots = float(item.lots or 0.0)
        fee = float(item.fee or 0.0)
        cost_value = max(buy_price, 0.0) * lots + fee
        current_price = float(price_map.get(symbol) or buy_price)
        current_value = max(current_price, 0.0) * lots
        pnl_value = current_value - cost_value
        pnl_pct = (pnl_value / cost_value) if cost_value else 0.0
        total_value += current_value
        total_cost += cost_value
        rows.append(
            {
                "symbol": symbol,
                "name": str(stock_payload.get("name") or symbol),
                "market": str(stock_payload.get("market") or ""),
                "raw_sector": str(stock_payload.get("raw_sector") or ""),
                "sector": str(stock_payload.get("sector") or "未分类"),
                "buy_price": buy_price,
                "lots": lots,
                "fee": fee,
                "buy_date": item.buy_date,
                "cost_value": cost_value,
                "current_price": current_price,
                "current_value": current_value,
                "pnl_value": pnl_value,
                "pnl_pct": pnl_pct,
            }
        )

    snapshots = [
        HoldingSnapshot(
            symbol=str(item["symbol"]),
            name=str(item["name"]),
            market=str(item["market"]),
            raw_sector=str(item["raw_sector"]),
            sector=str(item["sector"]),
            buy_price=float(item["buy_price"]),
            lots=float(item["lots"]),
            fee=float(item["fee"]),
            buy_date=item["buy_date"],
            cost_value=float(item["cost_value"]),
            current_price=float(item["current_price"]),
            current_value=float(item["current_value"]),
            pnl_value=float(item["pnl_value"]),
            pnl_pct=float(item["pnl_pct"]),
            weight=(float(item["current_value"]) / total_value) if total_value else 0.0,
        )
        for item in rows
    ]
    return snapshots, total_value, total_cost, as_of


def load_watch_target_snapshots(db: Session, user_id: int) -> tuple[list[HoldingSnapshot], float, float, date | None]:
    watch_targets = (
        db.query(UserWatchTarget)
        .filter(UserWatchTarget.user_id == user_id)
        .order_by(UserWatchTarget.updated_at.desc(), UserWatchTarget.symbol.asc())
        .all()
    )
    symbols = [str(item.symbol) for item in watch_targets]
    if not symbols:
        return [], 0.0, 0.0, None

    price_map, as_of = latest_price_map(db, symbols)
    stock_map = build_stock_snapshot_map(db, symbols)
    snapshot_date = as_of or date.today()
    total_value = float(len(symbols)) * WATCH_TARGET_NOTIONAL_UNIT
    rows: list[dict[str, object]] = []
    for symbol in symbols:
        stock_payload = stock_map.get(symbol, {})
        current_price = float(price_map.get(symbol) or 0.0)
        rows.append(
            {
                "symbol": symbol,
                "name": str(stock_payload.get("name") or symbol),
                "market": str(stock_payload.get("market") or ""),
                "raw_sector": str(stock_payload.get("raw_sector") or ""),
                "sector": str(stock_payload.get("sector") or "未分类"),
                "buy_price": current_price,
                "lots": 1.0,
                "fee": 0.0,
                "buy_date": snapshot_date,
                "cost_value": WATCH_TARGET_NOTIONAL_UNIT,
                "current_price": current_price,
                "current_value": WATCH_TARGET_NOTIONAL_UNIT,
                "pnl_value": 0.0,
                "pnl_pct": 0.0,
            }
        )

    snapshots = [
        HoldingSnapshot(
            symbol=str(item["symbol"]),
            name=str(item["name"]),
            market=str(item["market"]),
            raw_sector=str(item["raw_sector"]),
            sector=str(item["sector"]),
            buy_price=float(item["buy_price"]),
            lots=float(item["lots"]),
            fee=float(item["fee"]),
            buy_date=item["buy_date"],
            cost_value=float(item["cost_value"]),
            current_price=float(item["current_price"]),
            current_value=float(item["current_value"]),
            pnl_value=float(item["pnl_value"]),
            pnl_pct=float(item["pnl_pct"]),
            weight=(float(item["current_value"]) / total_value) if total_value else 0.0,
        )
        for item in rows
    ]
    return snapshots, total_value, total_value, as_of
