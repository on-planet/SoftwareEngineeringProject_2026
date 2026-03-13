from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.common import IdOut
from app.schemas.pagination import Page
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE, INSIDER_PAGE_EXAMPLE
from app.schemas.insider_trade import InsiderTradeOut, InsiderTradeCreate, InsiderTradeUpdate
from app.services.insider_trade_service import (
    list_insider_trades,
    create_insider_trade,
    update_insider_trade,
    delete_insider_trade,
)
from app.utils.query_params import pagination_params, sort_params

router = APIRouter(tags=["insider"])


@router.get(
    "/stock/{symbol}/insider",
    response_model=Page[InsiderTradeOut],
    responses={
        200: {"content": {"application/json": {"example": INSIDER_PAGE_EXAMPLE}}},
        404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def list_insider_route(
    symbol: str,
    start: date | None = Query(None),
    end: date | None = Query(None),
    trade_type: str | None = Query(None, alias="type"),
    trade_types: list[str] | None = Query(None),
    min_shares: float | None = Query(None, ge=0),
    max_shares: float | None = Query(None, ge=0),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    """获取增减持记录。"""
    types_filter = trade_types or ([trade_type] if trade_type else None)
    items, total = list_insider_trades(
        db,
        symbol,
        limit=paging["limit"],
        offset=paging["offset"],
        start=start,
        end=end,
        trade_types=types_filter,
        min_shares=min_shares,
        max_shares=max_shares,
        sort=sorting["sort"],
    )
    return {"items": items, "total": total, **paging}


@router.post(
    "/insider",
    response_model=InsiderTradeOut,
    responses={400: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def create_insider_route(payload: InsiderTradeCreate, db: Session = Depends(get_db)):
    """创建增减持记录。"""
    return create_insider_trade(db, payload)


@router.patch(
    "/insider/{trade_id}",
    response_model=InsiderTradeOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def update_insider_route(trade_id: int, payload: InsiderTradeUpdate, db: Session = Depends(get_db)):
    """更新增减持记录。"""
    item = update_insider_trade(db, trade_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Insider trade not found")
    return item


@router.delete(
    "/insider/{trade_id}",
    response_model=IdOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def delete_insider_route(trade_id: int, db: Session = Depends(get_db)):
    """删除增减持记录。"""
    ok = delete_insider_trade(db, trade_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Insider trade not found")
    return {"id": trade_id}
