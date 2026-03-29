from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.daily_prices import DailyPrice
from app.models.stocks import Stock
from app.models.user_portfolio import UserPortfolio
from app.services.cache_utils import build_cache_key, item_to_dict
from app.schemas.portfolio_analysis import (
    ConcentrationItem,
    ExposureItem,
    PortfolioAnalysisOut,
    PortfolioItemAnalysis,
    PortfolioSummary,
)
from etl.utils.sector_taxonomy import normalize_sector_name

PORTFOLIO_ANALYSIS_CACHE_TTL = 600


def _latest_prices_map(db: Session, symbols: list[str]):
    if not symbols:
        return {}
    subquery = (
        db.query(DailyPrice.symbol, func.max(DailyPrice.date).label("latest_date"))
        .filter(DailyPrice.symbol.in_(symbols))
        .group_by(DailyPrice.symbol)
        .subquery()
    )
    rows = (
        db.query(DailyPrice.symbol, DailyPrice.close)
        .join(
            subquery,
            (DailyPrice.symbol == subquery.c.symbol)
            & (DailyPrice.date == subquery.c.latest_date),
        )
        .all()
    )
    return {symbol: float(close or 0) for symbol, close in rows}


def get_portfolio_analysis(db: Session, user_id: int, top_n: int = 5) -> PortfolioAnalysisOut:
    cache_key = build_cache_key("user:portfolio:analysis", user_id=user_id, top_n=top_n)
    cached = get_json(cache_key)
    if isinstance(cached, dict):
        try:
            return PortfolioAnalysisOut(**cached)
        except Exception:
            pass

    # 优化：一次性查询所有持仓数据
    holdings = db.query(UserPortfolio).filter(UserPortfolio.user_id == user_id).all()
    
    if not holdings:
        # 空持仓时返回空分析结果
        return PortfolioAnalysisOut(
            user_id=user_id,
            items=[],
            summary=PortfolioSummary(
                total_cost=0.0,
                total_value=0.0,
                total_pnl=0.0,
                total_pnl_pct=0.0,
            ),
            sector_exposure=[],
            top_holdings=[],
        )
    
    symbols = [item.symbol for item in holdings]
    
    # 优化：批量查询价格和行业信息，避免 N+1
    price_map = _latest_prices_map(db, symbols)
    sector_map = {
        symbol: normalize_sector_name(sector)
        for symbol, sector in db.query(Stock.symbol, Stock.sector).filter(Stock.symbol.in_(symbols)).all()
    }

    items: list[PortfolioItemAnalysis] = []
    total_cost = 0.0
    total_value = 0.0

    for item in holdings:
        latest_price = price_map.get(item.symbol, 0.0)
        cost = item.avg_cost * item.shares
        value = latest_price * item.shares
        pnl = value - cost
        pnl_pct = (pnl / cost) if cost else 0.0
        total_cost += cost
        total_value += value
        items.append(
            PortfolioItemAnalysis(
                symbol=item.symbol,
                shares=float(item.shares),
                avg_cost=float(item.avg_cost),
                latest_price=float(latest_price),
                pnl=float(pnl),
                pnl_pct=float(pnl_pct),
                sector=sector_map.get(item.symbol),
            )
        )

    total_pnl = total_value - total_cost
    total_pnl_pct = (total_pnl / total_cost) if total_cost else 0.0

    exposure_bucket: dict[str, float] = defaultdict(float)
    for item in items:
        sector = normalize_sector_name(item.sector)
        exposure_bucket[sector] += item.latest_price * item.shares

    sector_exposure = [
        ExposureItem(
            sector=sector,
            value=value,
            weight=(value / total_value) if total_value else 0.0,
        )
        for sector, value in exposure_bucket.items()
    ]
    sector_exposure.sort(key=lambda x: x.weight, reverse=True)

    concentration = [
        ConcentrationItem(
            symbol=item.symbol,
            value=item.latest_price * item.shares,
            weight=(item.latest_price * item.shares / total_value) if total_value else 0.0,
        )
        for item in items
    ]
    concentration.sort(key=lambda x: x.weight, reverse=True)
    top_holdings = concentration[:top_n]

    output = PortfolioAnalysisOut(
        user_id=user_id,
        items=items,
        summary=PortfolioSummary(
            total_cost=total_cost,
            total_value=total_value,
            total_pnl=total_pnl,
            total_pnl_pct=total_pnl_pct,
        ),
        sector_exposure=sector_exposure,
        top_holdings=top_holdings,
    )
    set_json(cache_key, item_to_dict(output), ttl=PORTFOLIO_ANALYSIS_CACHE_TTL)
    return output
