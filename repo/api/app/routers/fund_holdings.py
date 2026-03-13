from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.common import IdOut
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE
from app.schemas.fund_holdings import FundHoldingOut, FundHoldingCreate, FundHoldingUpdate
from app.schemas.fund_holdings_series import FundHoldingSeriesOut, StockHoldingSeriesOut
from app.schemas.fund_holdings_stats import FundHoldingFundStat, FundHoldingStockStat
from app.schemas.pagination import Page
from app.services.fund_holdings_service import (
    list_fund_holdings,
    list_fund_stats,
    list_stock_stats,
    list_fund_series,
    list_stock_series,
    create_fund_holding,
    update_fund_holding,
    delete_fund_holding,
)
from app.utils.query_params import pagination_params, sort_params

router = APIRouter(tags=["fund_holdings"])


@router.get(
    "/fund_holdings",
    response_model=Page[FundHoldingOut],
    responses={
        200: {"content": {"application/json": {"example": {"items": [], "total": 0, "limit": 50, "offset": 0}}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def list_fund_holdings_route(
    fund_code: str | None = Query(None),
    symbol: str | None = Query(None),
    start: date | None = Query(None),
    end: date | None = Query(None),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    items, total = list_fund_holdings(
        db,
        fund_code=fund_code,
        symbol=symbol,
        start=start,
        end=end,
        limit=paging["limit"],
        offset=paging["offset"],
        sort=sorting["sort"],
    )
    return {"items": items, "total": total, **paging}


@router.get(
    "/fund_holdings/series/fund",
    response_model=FundHoldingSeriesOut,
    responses={
        200: {"content": {"application/json": {"example": {"fund_code": "000001", "items": []}}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def list_fund_series_route(
    fund_code: str = Query(...),
    db: Session = Depends(get_db),
):
    items = list_fund_series(db, fund_code=fund_code)
    return {"fund_code": fund_code, "items": items}


@router.get(
    "/fund_holdings/series/stock",
    response_model=StockHoldingSeriesOut,
    responses={
        200: {"content": {"application/json": {"example": {"symbol": "000001.SH", "items": []}}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def list_stock_series_route(
    symbol: str = Query(...),
    db: Session = Depends(get_db),
):
    items = list_stock_series(db, symbol=symbol)
    return {"symbol": symbol, "items": items}


@router.get(
    "/fund_holdings/stats/fund",
    response_model=list[FundHoldingFundStat],
    responses={
        200: {"content": {"application/json": {"example": []}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def list_fund_stats_route(
    report_date: date | None = Query(None),
    db: Session = Depends(get_db),
):
    return list_fund_stats(db, report_date=report_date)


@router.get(
    "/fund_holdings/stats/stock",
    response_model=list[FundHoldingStockStat],
    responses={
        200: {"content": {"application/json": {"example": []}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def list_stock_stats_route(
    report_date: date | None = Query(None),
    db: Session = Depends(get_db),
):
    return list_stock_stats(db, report_date=report_date)


@router.post(
    "/fund_holdings",
    response_model=FundHoldingOut,
    responses={400: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def create_fund_holding_route(payload: FundHoldingCreate, db: Session = Depends(get_db)):
    return create_fund_holding(db, payload)


@router.patch(
    "/fund_holdings/{fund_code}/{symbol}/{report_date}",
    response_model=FundHoldingOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def update_fund_holding_route(
    fund_code: str,
    symbol: str,
    report_date: date,
    payload: FundHoldingUpdate,
    db: Session = Depends(get_db),
):
    item = update_fund_holding(db, fund_code, symbol, report_date, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Fund holding not found")
    return item


@router.delete(
    "/fund_holdings/{fund_code}/{symbol}/{report_date}",
    response_model=IdOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def delete_fund_holding_route(
    fund_code: str,
    symbol: str,
    report_date: date,
    db: Session = Depends(get_db),
):
    ok = delete_fund_holding(db, fund_code, symbol, report_date)
    if not ok:
        raise HTTPException(status_code=404, detail="Fund holding not found")
    return {"id": 0}
