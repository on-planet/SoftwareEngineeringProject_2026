from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE, RISK_SERIES_EXAMPLE
from app.schemas.risk_series import RiskSeriesOut
from app.services.risk_series_service import get_risk_series

router = APIRouter(tags=["risk"])


@router.get(
    "/risk/{symbol}/series",
    response_model=RiskSeriesOut,
    responses={
        200: {"content": {"application/json": {"example": RISK_SERIES_EXAMPLE}}},
        404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def get_risk_series_route(
    symbol: str,
    window: int = Query(20, ge=2, le=200),
    limit: int = Query(200, ge=20, le=500),
    end: date | None = Query(None),
    start: date | None = Query(None),
    db: Session = Depends(get_db),
):
    """获取风险指标历史序列。"""
    items, cache_hit = get_risk_series(db, symbol, window, limit, end, start)
    return {"symbol": symbol, "items": items, "cache_hit": cache_hit}
