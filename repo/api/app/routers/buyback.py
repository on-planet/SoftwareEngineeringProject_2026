from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.common import IdOut
from app.schemas.pagination import Page
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE, BUYBACK_PAGE_EXAMPLE
from app.schemas.buyback import BuybackOut, BuybackCreate, BuybackUpdate
from app.services.buyback_service import (
    list_buyback,
    create_buyback,
    update_buyback,
    delete_buyback,
)
from app.utils.query_params import pagination_params, sort_params

router = APIRouter(tags=["buyback"])


@router.get(
    "/stock/{symbol}/buyback",
    response_model=Page[BuybackOut],
    responses={
        200: {"content": {"application/json": {"example": BUYBACK_PAGE_EXAMPLE}}},
        404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def list_buyback_route(
    symbol: str,
    start: date | None = Query(None),
    end: date | None = Query(None),
    min_amount: float | None = Query(None, ge=0),
    max_amount: float | None = Query(None, ge=0),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    """获取回购披露。"""
    items, total = list_buyback(
        db,
        symbol,
        limit=paging["limit"],
        offset=paging["offset"],
        start=start,
        end=end,
        min_amount=min_amount,
        max_amount=max_amount,
        sort=sorting["sort"],
    )
    return {"items": items, "total": total, **paging}


@router.post(
    "/buyback",
    response_model=BuybackOut,
    responses={400: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def create_buyback_route(payload: BuybackCreate, db: Session = Depends(get_db)):
    """创建回购记录。"""
    return create_buyback(db, payload)


@router.patch(
    "/buyback/{symbol}/{buyback_date}",
    response_model=BuybackOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def update_buyback_route(
    symbol: str,
    buyback_date: date,
    payload: BuybackUpdate,
    db: Session = Depends(get_db),
):
    """更新回购记录。"""
    item = update_buyback(db, symbol, buyback_date, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Buyback not found")
    return item


@router.delete(
    "/buyback/{symbol}/{buyback_date}",
    response_model=IdOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def delete_buyback_route(symbol: str, buyback_date: date, db: Session = Depends(get_db)):
    """删除回购记录。"""
    ok = delete_buyback(db, symbol, buyback_date)
    if not ok:
        raise HTTPException(status_code=404, detail="Buyback not found")
    return {"id": 0}
