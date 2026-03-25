from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.bond_market import BondMarketQuoteOut, BondMarketTradeOut
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE
from app.schemas.pagination import Page
from app.services.bond_market_service import list_bond_market_quotes, list_bond_market_trades
from app.utils.query_params import pagination_params, sort_params

router = APIRouter(tags=["bond_market"])


@router.get(
    "/bond/market/quote",
    response_model=Page[BondMarketQuoteOut],
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def list_bond_market_quotes_route(
    keyword: str | None = Query(None),
    refresh: bool = Query(False),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    items, total = list_bond_market_quotes(
        db,
        keyword=keyword,
        limit=paging["limit"],
        offset=paging["offset"],
        sort=sorting["sort"],
        refresh=refresh,
    )
    return {"items": items, "total": total, **paging}


@router.get(
    "/bond/market/trade",
    response_model=Page[BondMarketTradeOut],
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def list_bond_market_trades_route(
    keyword: str | None = Query(None),
    refresh: bool = Query(False),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    items, total = list_bond_market_trades(
        db,
        keyword=keyword,
        limit=paging["limit"],
        offset=paging["offset"],
        sort=sorting["sort"],
        refresh=refresh,
    )
    return {"items": items, "total": total, **paging}
