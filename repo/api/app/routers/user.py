from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.auth_user import AuthUser
from app.routers.auth import get_current_user
from app.schemas.common import IdOut
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE, PORTFOLIO_ANALYSIS_EXAMPLE, PORTFOLIO_PAGE_EXAMPLE
from app.schemas.pagination import Page
from app.schemas.portfolio_analysis import PortfolioAnalysisOut
from app.schemas.user import PortfolioBatchIn, PortfolioCreate, PortfolioOut, PortfolioUpdate
from app.services.portfolio_analysis_service import get_portfolio_analysis
from app.services.user_service import (
    batch_upsert_portfolio,
    create_portfolio,
    delete_portfolio,
    get_user_portfolio,
    update_portfolio,
)
from app.utils.query_params import pagination_params

router = APIRouter(tags=["user"])


def _ensure_user_scope(user_id: int, current_user: AuthUser) -> None:
    if int(current_user.id) != int(user_id):
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get(
    "/user/{user_id}/portfolio",
    response_model=Page[PortfolioOut],
    responses={
        200: {"content": {"application/json": {"example": PORTFOLIO_PAGE_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def get_portfolio(
    user_id: int,
    symbol: str | None = Query(None),
    min_shares: float | None = Query(None, ge=0),
    max_shares: float | None = Query(None, ge=0),
    paging: dict = Depends(pagination_params),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    _ensure_user_scope(user_id, current_user)
    items, total = get_user_portfolio(
        db,
        user_id,
        symbol=symbol,
        min_shares=min_shares,
        max_shares=max_shares,
        limit=paging["limit"],
        offset=paging["offset"],
    )
    return {"items": items, "total": total, **paging}


@router.get(
    "/user/{user_id}/portfolio/analysis",
    response_model=PortfolioAnalysisOut,
    responses={
        200: {"content": {"application/json": {"example": PORTFOLIO_ANALYSIS_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def get_portfolio_analysis_route(
    user_id: int,
    top_n: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    _ensure_user_scope(user_id, current_user)
    return get_portfolio_analysis(db, user_id, top_n=top_n)


@router.post(
    "/user/portfolio",
    response_model=PortfolioOut,
    responses={
        400: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def create_portfolio_route(
    payload: PortfolioCreate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    _ensure_user_scope(payload.user_id, current_user)
    return create_portfolio(db, payload)


@router.patch(
    "/user/{user_id}/portfolio/{symbol}",
    response_model=PortfolioOut,
    responses={
        404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def update_portfolio_route(
    user_id: int,
    symbol: str,
    payload: PortfolioUpdate,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    _ensure_user_scope(user_id, current_user)
    item = update_portfolio(db, user_id, symbol, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    return item


@router.post(
    "/user/{user_id}/portfolio/batch",
    response_model=list[PortfolioOut],
    responses={
        400: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def upsert_portfolio_batch(
    user_id: int,
    payload: PortfolioBatchIn,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    _ensure_user_scope(user_id, current_user)
    if payload.user_id != user_id:
        raise HTTPException(status_code=400, detail="User id mismatch")
    return batch_upsert_portfolio(db, user_id, payload.items)


@router.delete(
    "/user/{user_id}/portfolio/{symbol}",
    response_model=IdOut,
    responses={
        404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def delete_portfolio_route(
    user_id: int,
    symbol: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    _ensure_user_scope(user_id, current_user)
    ok = delete_portfolio(db, user_id, symbol)
    if not ok:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    return {"id": user_id}
