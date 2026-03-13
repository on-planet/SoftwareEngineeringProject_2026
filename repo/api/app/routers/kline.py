from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE, KLINE_SERIES_EXAMPLE
from app.schemas.kline import KlineSeriesOut
from app.services.kline_service import get_index_kline

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
    limit: int = Query(200, ge=10, le=500),
    end: date | None = Query(None),
    start: date | None = Query(None),
    db: Session = Depends(get_db),
):
    """获取指数 K 线数据。"""
    items = get_index_kline(db, symbol, limit, end, start)
    return {"symbol": symbol, "items": items}
