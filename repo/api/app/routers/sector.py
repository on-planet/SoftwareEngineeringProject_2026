from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE, SECTOR_EXPOSURE_EXAMPLE
from app.schemas.sector_exposure import SectorExposureOut
from app.services.sector_exposure_service import get_sector_exposure

router = APIRouter(tags=["sector"])


@router.get(
    "/sector/exposure",
    response_model=SectorExposureOut,
    responses={
        200: {"content": {"application/json": {"example": SECTOR_EXPOSURE_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def get_sector_exposure_route(
    market: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("desc", pattern="^(asc|desc)$"),
    as_of: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """获取行业分布。"""
    items = get_sector_exposure(db, market, limit, offset, sort, as_of)
    return {"market": market, "items": items}
