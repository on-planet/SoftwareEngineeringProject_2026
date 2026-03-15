from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Query

from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE, KLINE_SERIES_EXAMPLE
from app.schemas.kline import KlineSeriesOut
from app.services.kline_service import get_index_kline, get_stock_kline

router = APIRouter(tags=["kline"])


@router.get(
    "/index/{symbol}/kline",
    response_model=KlineSeriesOut,
    responses={
        200: {"content": {"application/json": {"example": KLINE_SERIES_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def get_index_kline_route(
    symbol: str,
    period: str = Query("day", pattern="^(1m|30m|60m|day|week|month|quarter|year)$"),
    limit: int = Query(200, ge=10, le=500),
    end: date | None = Query(None),
    start: date | None = Query(None),
):
    items = get_index_kline(symbol, period=period, limit=limit, end=end, start=start)
    return {"symbol": symbol.upper(), "period": period, "items": items}


@router.get(
    "/stock/{symbol}/kline",
    response_model=KlineSeriesOut,
    responses={
        200: {"content": {"application/json": {"example": KLINE_SERIES_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def get_stock_kline_route(
    symbol: str,
    period: str = Query("day", pattern="^(1m|30m|60m|day|week|month|quarter|year)$"),
    limit: int = Query(200, ge=10, le=500),
    end: date | None = Query(None),
    start: date | None = Query(None),
):
    items = get_stock_kline(symbol, period=period, limit=limit, end=end, start=start)
    return {"symbol": symbol.upper(), "period": period, "items": items}
