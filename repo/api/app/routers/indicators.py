from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE, INDICATOR_SERIES_EXAMPLE
from app.schemas.indicators import IndicatorSeriesOut
from app.services.indicator_service import AVAILABLE_INDICATORS, get_indicator_series

router = APIRouter(tags=["indicators"])


@router.get(
    "/stock/{symbol}/indicators",
    response_model=IndicatorSeriesOut,
    responses={
        200: {"content": {"application/json": {"example": INDICATOR_SERIES_EXAMPLE}}},
        404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def get_indicators_route(
    symbol: str,
    indicator: str = Query("ma"),
    window: int = Query(14, ge=1, le=200),
    limit: int = Query(200, ge=10, le=500),
    end: date | None = Query(None),
    start: date | None = Query(None),
):
    indicator = indicator.lower()
    if indicator not in AVAILABLE_INDICATORS:
        raise HTTPException(status_code=400, detail=f"Unsupported indicator. Available: {', '.join(AVAILABLE_INDICATORS)}")
    items, lines, params, cache_hit = get_indicator_series(symbol, indicator, window, limit, end, start)
    return {
        "symbol": symbol,
        "indicator": indicator,
        "window": window,
        "lines": lines,
        "params": params,
        "items": items,
        "cache_hit": cache_hit,
    }
