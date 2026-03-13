from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.common import IdOut
from app.schemas.pagination import Page
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE, FINANCIALS_PAGE_EXAMPLE
from app.schemas.financials import FinancialOut, FinancialCreate, FinancialUpdate
from app.services.financial_service import (
    list_financials,
    create_financial,
    update_financial,
    delete_financial,
)
from app.utils.query_params import pagination_params, sort_params

router = APIRouter(tags=["financials"])


@router.get(
    "/stock/{symbol}/financials",
    response_model=Page[FinancialOut],
    responses={
        200: {"content": {"application/json": {"example": FINANCIALS_PAGE_EXAMPLE}}},
        404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def list_financials_route(
    symbol: str,
    period: str | None = Query(None),
    min_revenue: float | None = Query(None),
    min_net_income: float | None = Query(None),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    """获取财务报表。"""
    items, total = list_financials(
        db,
        symbol,
        limit=paging["limit"],
        offset=paging["offset"],
        period=period,
        min_revenue=min_revenue,
        min_net_income=min_net_income,
        sort=sorting["sort"],
    )
    return {"items": items, "total": total, **paging}


@router.post(
    "/financials",
    response_model=FinancialOut,
    responses={400: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def create_financial_route(payload: FinancialCreate, db: Session = Depends(get_db)):
    """创建财务报表记录。"""
    return create_financial(db, payload)


@router.patch(
    "/financials/{symbol}/{period}",
    response_model=FinancialOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def update_financial_route(
    symbol: str,
    period: str,
    payload: FinancialUpdate,
    db: Session = Depends(get_db),
):
    """更新财务报表记录。"""
    item = update_financial(db, symbol, period, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Financial record not found")
    return item


@router.delete(
    "/financials/{symbol}/{period}",
    response_model=IdOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def delete_financial_route(symbol: str, period: str, db: Session = Depends(get_db)):
    """删除财务报表记录。"""
    ok = delete_financial(db, symbol, period)
    if not ok:
        raise HTTPException(status_code=404, detail="Financial record not found")
    return {"id": 0}
