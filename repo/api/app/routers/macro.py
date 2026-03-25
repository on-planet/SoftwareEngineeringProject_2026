from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.common import IdOut
from app.schemas.macro import MacroOut, MacroCreate, MacroUpdate
from app.schemas.macro_series import MacroSeriesOut
from app.schemas.pagination import Page
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE, MACRO_PAGE_EXAMPLE, MACRO_SERIES_EXAMPLE
from app.services.macro_service import (
    create_macro,
    delete_macro,
    get_cached_macro,
    get_macro_series,
    list_macro,
    list_macro_snapshot,
    update_macro,
)
from app.utils.query_params import pagination_params, sort_params

router = APIRouter(tags=["macro"])


@router.get(
    "/macro",
    response_model=Page[MacroOut],
    responses={
        200: {"content": {"application/json": {"example": MACRO_PAGE_EXAMPLE}}},
        404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def list_macro_route(
    start: date | None = None,
    end: date | None = None,
    as_of: date | None = None,
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    """获取宏观指标列表。"""
    cached = get_cached_macro(as_of, start, end, sorting["sort"])
    if cached is None:
        items = list_macro(db, start, end, sorting["sort"])
    else:
        items = cached
    total = len(items)
    sliced = items[paging["offset"] : paging["offset"] + paging["limit"]]
    return {"items": sliced, "total": total, **paging}


@router.get(
    "/macro/snapshot",
    response_model=Page[MacroOut],
    responses={
        404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def list_macro_snapshot_route(
    as_of: date | None = None,
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    """鑾峰彇姣忎釜瀹忚鎸囨爣鐨勬渶鏂板揩鐓с€?"""
    items = list_macro_snapshot(db, as_of=as_of, sort=sorting["sort"])
    total = len(items)
    sliced = items[paging["offset"] : paging["offset"] + paging["limit"]]
    return {"items": sliced, "total": total, **paging}


@router.get(
    "/macro/series/{key}",
    response_model=MacroSeriesOut,
    responses={
        200: {"content": {"application/json": {"example": MACRO_SERIES_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def get_macro_series_route(
    key: str,
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
):
    """获取宏观指标序列。"""
    items = get_macro_series(db, key, start, end)
    return {"key": key, "items": items}


@router.post(
    "/macro",
    response_model=MacroOut,
    responses={400: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def create_macro_route(payload: MacroCreate, db: Session = Depends(get_db)):
    """创建宏观指标记录。"""
    return create_macro(db, payload)


@router.patch(
    "/macro/{key}/{macro_date}",
    response_model=MacroOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def update_macro_route(
    key: str,
    macro_date: date,
    payload: MacroUpdate,
    db: Session = Depends(get_db),
):
    """更新宏观指标记录。"""
    item = update_macro(db, key, macro_date, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Macro not found")
    return item


@router.delete(
    "/macro/{key}/{macro_date}",
    response_model=IdOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def delete_macro_route(key: str, macro_date: date, db: Session = Depends(get_db)):
    """删除宏观指标记录。"""
    ok = delete_macro(db, key, macro_date)
    if not ok:
        raise HTTPException(status_code=404, detail="Macro not found")
    return {"id": 0}
