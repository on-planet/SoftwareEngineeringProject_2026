from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.heatmap import HeatmapItemOut
from app.schemas.pagination import Page
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE, HEATMAP_PAGE_EXAMPLE
from app.services.heatmap_service import get_cached_heatmap, get_heatmap
from app.utils.query_params import sort_params, pagination_params

router = APIRouter(tags=["heatmap"])


@router.get(
    "/heatmap",
    response_model=Page[HeatmapItemOut],
    responses={
        200: {"content": {"application/json": {"example": HEATMAP_PAGE_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def get_heatmap_route(
    sector: str | None = Query(None),
    market: str | None = Query(None),
    min_change: float | None = Query(None),
    max_change: float | None = Query(None),
    as_of: date | None = Query(None),
    sorting: dict = Depends(sort_params),
    paging: dict = Depends(pagination_params),
    db: Session = Depends(get_db),
):
    """获取行业热力图。"""
    items = get_cached_heatmap(as_of, sector, market, min_change, max_change, sorting["sort"])
    if items is None:
        items = get_heatmap(db, sorting["sort"], sector, market, min_change, max_change)
    total = len(items)
    sliced = items[paging["offset"] : paging["offset"] + paging["limit"]]
    return {"items": sliced, "total": total, **paging}
