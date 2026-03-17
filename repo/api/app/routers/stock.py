from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.common import IdOut
from app.schemas.risk import RiskOut
from app.schemas.stock import (
    DailyPriceOut,
    StockCreate,
    StockExtrasOut,
    StockOut,
    StockOverviewOut,
    StockUpdate,
    StockWithRiskOut,
)
from app.schemas.fundamental import FundamentalOut, FundamentalCreate, FundamentalUpdate
from app.schemas.pagination import Page
from app.schemas.research import ResearchPanelOut
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE, STOCK_WITH_RISK_EXAMPLE
from app.services.stock_service import (
    list_stocks,
    get_stock_profile,
    get_stock_overview_profile,
    get_stock_profile_extras,
    get_stock_daily,
    create_stock,
    update_stock,
    delete_stock,
)
from app.services.risk_service import get_risk_snapshot
from app.services.score_service import (
    get_fundamental_score,
    create_fundamental_score,
    update_fundamental_score,
    delete_fundamental_score,
)
from app.services.research_service import get_stock_research
from app.utils.errors import ensure_found
from app.utils.query_params import pagination_params, sort_params
from app.utils.validators import validate_symbol_match

router = APIRouter(tags=["stock"])


@router.get(
    "/stocks",
    response_model=Page[StockOut],
    responses={
        200: {"content": {"application/json": {"example": {"items": [], "total": 0, "limit": 100, "offset": 0}}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def list_stocks_route(
    market: str | None = Query(None, pattern="^(A|HK|US)$"),
    keyword: str | None = Query(None),
    sorting: dict = Depends(sort_params),
    paging: dict = Depends(pagination_params),
):
    items, total = list_stocks(
        market=market,
        keyword=keyword,
        limit=paging["limit"],
        offset=paging["offset"],
        sort=sorting["sort"],
    )
    return {"items": items, "total": total, **paging}


@router.get(
    "/stock/{symbol}",
    response_model=StockWithRiskOut,
    responses={
        200: {"content": {"application/json": {"example": STOCK_WITH_RISK_EXAMPLE}}},
        404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def get_stock(symbol: str, prefer_live: bool = Query(False)):
    """获取股票基本信息。"""
    stock = ensure_found(get_stock_profile(symbol, prefer_live=prefer_live), "Stock not found")
    risk_payload = get_risk_snapshot(symbol)
    if isinstance(stock, dict):
        result = StockWithRiskOut(**stock)
    else:
        result = StockWithRiskOut.from_orm(stock)
    if risk_payload:
        result.risk = RiskOut(
            symbol=symbol,
            max_drawdown=risk_payload.get("max_drawdown"),
            volatility=risk_payload.get("volatility"),
            as_of=risk_payload.get("as_of"),
            cache_hit=risk_payload.get("cache_hit"),
        )
    return result


@router.get(
    "/stock/{symbol}/overview",
    response_model=StockOverviewOut,
    responses={
        404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def get_stock_overview(symbol: str, prefer_live: bool = Query(False)):
    stock = ensure_found(get_stock_overview_profile(symbol, prefer_live=prefer_live), "Stock not found")
    risk_payload = get_risk_snapshot(symbol)
    fundamental = get_fundamental_score(symbol)
    payload = dict(stock) if isinstance(stock, dict) else StockOverviewOut.from_orm(stock).model_dump()
    if risk_payload:
        payload["risk"] = RiskOut(
            symbol=symbol,
            max_drawdown=risk_payload.get("max_drawdown"),
            volatility=risk_payload.get("volatility"),
            as_of=risk_payload.get("as_of"),
            cache_hit=risk_payload.get("cache_hit"),
        )
    payload["fundamental"] = fundamental
    return StockOverviewOut(**payload)


@router.get(
    "/stock/{symbol}/extras",
    response_model=StockExtrasOut,
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def get_stock_extras(symbol: str, prefer_live: bool = Query(False)):
    return get_stock_profile_extras(symbol, prefer_live=prefer_live)


@router.post(
    "/stock",
    response_model=StockOut,
    responses={400: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def create_stock_route(payload: StockCreate, db: Session = Depends(get_db)):
    """创建股票基础信息。"""
    return create_stock(db, payload)


@router.patch(
    "/stock/{symbol}",
    response_model=StockOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def update_stock_route(symbol: str, payload: StockUpdate, db: Session = Depends(get_db)):
    """更新股票基础信息。"""
    item = update_stock(db, symbol, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Stock not found")
    return item


@router.delete(
    "/stock/{symbol}",
    response_model=IdOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def delete_stock_route(symbol: str, db: Session = Depends(get_db)):
    """删除股票基础信息。"""
    ok = delete_stock(db, symbol)
    if not ok:
        raise HTTPException(status_code=404, detail="Stock not found")
    return {"id": 0}


@router.get(
    "/stock/{symbol}/daily",
    response_model=list[DailyPriceOut],
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def get_stock_daily_prices(
    symbol: str,
    start: date | None = None,
    end: date | None = None,
    min_volume: float | None = Query(None, ge=0),
    sorting: dict = Depends(sort_params),
):
    """获取股票日线数据。"""
    return get_stock_daily(symbol, start, end, sorting["sort"], min_volume)


@router.get(
    "/stock/{symbol}/fundamental",
    response_model=FundamentalOut | None,
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def get_fundamental(symbol: str):
    """获取基本面评分。"""
    return get_fundamental_score(symbol)


@router.get(
    "/stock/{symbol}/research",
    response_model=ResearchPanelOut,
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def get_research_panel(
    symbol: str,
    report_limit: int = Query(10, ge=1, le=50),
    forecast_limit: int = Query(10, ge=1, le=50),
):
    return get_stock_research(symbol, report_limit=report_limit, forecast_limit=forecast_limit)


@router.post(
    "/stock/{symbol}/fundamental",
    response_model=FundamentalOut,
    responses={400: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def create_fundamental(symbol: str, payload: FundamentalCreate, db: Session = Depends(get_db)):
    """创建基本面评分。"""
    validate_symbol_match(symbol, payload.symbol)
    return create_fundamental_score(db, payload)


@router.patch(
    "/stock/{symbol}/fundamental",
    response_model=FundamentalOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def update_fundamental(symbol: str, payload: FundamentalUpdate, db: Session = Depends(get_db)):
    """更新基本面评分。"""
    item = update_fundamental_score(db, symbol, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Fundamental score not found")
    return item


@router.delete(
    "/stock/{symbol}/fundamental",
    response_model=IdOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def delete_fundamental(symbol: str, db: Session = Depends(get_db)):
    """删除基本面评分。"""
    ok = delete_fundamental_score(db, symbol)
    if not ok:
        raise HTTPException(status_code=404, detail="Fundamental score not found")
    return {"id": 0}
