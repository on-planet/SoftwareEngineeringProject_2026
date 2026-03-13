from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE, INDEX_CONSTITUENTS_EXAMPLE
from app.schemas.index_constituent import IndexConstituentOut
from app.schemas.pagination import Page
from app.services.index_constituent_service import list_index_constituents
from app.utils.query_params import pagination_params

router = APIRouter(tags=["index"])


@router.get(
    "/index/{symbol}/constituents",
    response_model=Page[IndexConstituentOut],
    responses={
        200: {"content": {"application/json": {"example": INDEX_CONSTITUENTS_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def list_constituents_route(
    symbol: str,
    as_of: date | None = Query(None),
    paging: dict = Depends(pagination_params),
    db: Session = Depends(get_db),
):
    """获取指数成分股列表。"""
    items, total = list_index_constituents(db, symbol, as_of, paging["limit"], paging["offset"])
    return {"items": items, "total": total, **paging}
