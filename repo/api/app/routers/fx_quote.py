from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE
from app.schemas.fx_quote import FxPairQuoteOut, FxSpotQuoteOut, FxSwapQuoteOut
from app.schemas.pagination import Page
from app.services.fx_quote_service import list_fx_pair_quotes, list_fx_spot_quotes, list_fx_swap_quotes
from app.utils.query_params import pagination_params, sort_params

router = APIRouter(tags=["fx_quote"])


@router.get(
    "/fx/spot",
    response_model=Page[FxSpotQuoteOut],
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def list_fx_spot_quotes_route(
    pair: str | None = Query(None),
    refresh: bool = Query(False),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    items, total = list_fx_spot_quotes(
        db,
        pair=pair,
        limit=paging["limit"],
        offset=paging["offset"],
        sort=sorting["sort"],
        refresh=refresh,
    )
    return {"items": items, "total": total, **paging}


@router.get(
    "/fx/swap",
    response_model=Page[FxSwapQuoteOut],
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def list_fx_swap_quotes_route(
    pair: str | None = Query(None),
    refresh: bool = Query(False),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    items, total = list_fx_swap_quotes(
        db,
        pair=pair,
        limit=paging["limit"],
        offset=paging["offset"],
        sort=sorting["sort"],
        refresh=refresh,
    )
    return {"items": items, "total": total, **paging}


@router.get(
    "/fx/pair",
    response_model=Page[FxPairQuoteOut],
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def list_fx_pair_quotes_route(
    pair: str | None = Query(None),
    refresh: bool = Query(False),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    items, total = list_fx_pair_quotes(
        db,
        pair=pair,
        limit=paging["limit"],
        offset=paging["offset"],
        sort=sorting["sort"],
        refresh=refresh,
    )
    return {"items": items, "total": total, **paging}
