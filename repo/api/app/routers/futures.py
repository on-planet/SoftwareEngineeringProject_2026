from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE, FUTURES_PAGE_EXAMPLE, FUTURES_SERIES_EXAMPLE
from app.schemas.futures import FuturesOut, FuturesSeriesOut
from app.schemas.pagination import Page
from app.services.futures_service import get_futures_series, list_futures
from app.utils.query_params import sort_params

router = APIRouter(tags=["futures"])


@router.get(
    "/futures",
    response_model=Page[FuturesOut],
    responses={
        200: {"content": {"application/json": {"example": FUTURES_PAGE_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def list_futures_route(
    symbol: str | None = Query(None),
    start: date | None = Query(None),
    end: date | None = Query(None),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    items, total = list_futures(
        db,
        symbol=symbol,
        start=start,
        end=end,
        limit=limit,
        offset=offset,
        sort=sorting["sort"],
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get(
    "/futures/{symbol}/series",
    response_model=FuturesSeriesOut,
    responses={
        200: {"content": {"application/json": {"example": FUTURES_SERIES_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def get_futures_series_route(
    symbol: str,
    start: date | None = Query(None),
    end: date | None = Query(None),
    db: Session = Depends(get_db),
):
    items = get_futures_series(db, symbol=symbol, start=start, end=end)
    return {"symbol": symbol.upper(), "items": items}
