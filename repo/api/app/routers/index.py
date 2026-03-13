from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.common import IdOut
from app.schemas.index import IndexOut, IndexCreate, IndexUpdate
from app.schemas.pagination import Page
from app.schemas.error import ErrorResponse
from app.schemas.examples import INDEX_PAGE_EXAMPLE, ERROR_EXAMPLE
from app.services.index_service import list_indices, create_index, update_index, delete_index
from app.utils.errors import ensure_non_empty
from app.utils.query_params import sort_params, pagination_params

router = APIRouter(tags=["index"])


@router.get(
    "/index",
    response_model=Page[IndexOut],
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def get_indices(
    as_of: date | None = None,
    sorting: dict = Depends(sort_params),
    paging: dict = Depends(pagination_params),
    db: Session = Depends(get_db),
):
    """获取指数列表（T-1 日终）。"""
    items = list_indices(db, as_of, sorting["sort"])
    ensure_non_empty(items, "No index data")
    total = len(items)
    sliced = items[paging["offset"] : paging["offset"] + paging["limit"]]
    return {"items": sliced, "total": total, **paging}


@router.post(
    "/index",
    response_model=IndexOut,
    responses={400: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def create_index_route(payload: IndexCreate, db: Session = Depends(get_db)):
    """创建指数记录。"""
    return create_index(db, payload)


@router.patch(
    "/index/{symbol}/{index_date}",
    response_model=IndexOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def update_index_route(
    symbol: str,
    index_date: date,
    payload: IndexUpdate,
    db: Session = Depends(get_db),
):
    """更新指数记录。"""
    item = update_index(db, symbol, index_date, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Index not found")
    return item


@router.delete(
    "/index/{symbol}/{index_date}",
    response_model=IdOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def delete_index_route(symbol: str, index_date: date, db: Session = Depends(get_db)):
    """删除指数记录。"""
    ok = delete_index(db, symbol, index_date)
    if not ok:
        raise HTTPException(status_code=404, detail="Index not found")
    return {"id": 0}
