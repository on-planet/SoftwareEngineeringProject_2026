from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE
from app.schemas.pagination import Page
from app.schemas.stock_institute import (
    StockInstituteHoldDetailOut,
    StockInstituteHoldOut,
    StockInstituteRecommendDetailOut,
    StockInstituteRecommendOut,
)
from app.services.stock_institute_service import (
    list_stock_institute_hold_details,
    list_stock_institute_holds,
    list_stock_institute_recommendation_details,
    list_stock_institute_recommendations,
)
from app.utils.query_params import pagination_params, sort_params

router = APIRouter(tags=["stock_institute"])


@router.get(
    "/stock/institute/hold",
    response_model=Page[StockInstituteHoldOut],
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def list_stock_institute_holds_route(
    quarter: str | None = Query(None),
    symbol: str | None = Query(None),
    keyword: str | None = Query(None),
    refresh: bool = Query(False),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    items, total, target_quarter = list_stock_institute_holds(
        db,
        quarter=quarter,
        symbol=symbol,
        keyword=keyword,
        limit=paging["limit"],
        offset=paging["offset"],
        sort=sorting["sort"],
        refresh=refresh,
    )
    return {"items": items, "total": total, "limit": paging["limit"], "offset": paging["offset"], "quarter": target_quarter}


@router.get(
    "/stock/institute/hold/detail",
    response_model=Page[StockInstituteHoldDetailOut],
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def list_stock_institute_hold_details_route(
    symbol: str = Query(...),
    quarter: str | None = Query(None),
    refresh: bool = Query(False),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    items, total, _ = list_stock_institute_hold_details(
        db,
        symbol=symbol,
        quarter=quarter,
        limit=paging["limit"],
        offset=paging["offset"],
        sort=sorting["sort"],
        refresh=refresh,
    )
    return {"items": items, "total": total, **paging}


@router.get(
    "/stock/institute/recommend",
    response_model=Page[StockInstituteRecommendOut],
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def list_stock_institute_recommendations_route(
    category: str = Query("投资评级选股"),
    symbol: str | None = Query(None),
    keyword: str | None = Query(None),
    refresh: bool = Query(False),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    items, total = list_stock_institute_recommendations(
        db,
        category=category,
        symbol=symbol,
        keyword=keyword,
        limit=paging["limit"],
        offset=paging["offset"],
        sort=sorting["sort"],
        refresh=refresh,
    )
    return {"items": items, "total": total, **paging}


@router.get(
    "/stock/institute/recommend/detail",
    response_model=Page[StockInstituteRecommendDetailOut],
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def list_stock_institute_recommendation_details_route(
    symbol: str = Query(...),
    refresh: bool = Query(False),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    items, total = list_stock_institute_recommendation_details(
        db,
        symbol=symbol,
        limit=paging["limit"],
        offset=paging["offset"],
        sort=sorting["sort"],
        refresh=refresh,
    )
    return {"items": items, "total": total, **paging}
