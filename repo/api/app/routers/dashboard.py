from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.dashboard import DashboardOverviewOut, DashboardStatsOverviewOut
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE
from app.services.dashboard_service import get_dashboard_overview, get_dashboard_stats_overview

router = APIRouter(tags=["dashboard"])


@router.get(
    "/dashboard/overview",
    response_model=DashboardOverviewOut,
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def get_dashboard_overview_route(
    as_of: date | None = Query(None),
    index_limit: int = Query(20, ge=1, le=100),
    heatmap_limit: int = Query(24, ge=1, le=100),
    macro_limit: int = Query(12, ge=1, le=100),
    futures_limit: int = Query(8, ge=1, le=50),
    news_limit: int = Query(8, ge=1, le=50),
    db: Session = Depends(get_db),
):
    return get_dashboard_overview(
        db,
        as_of=as_of,
        index_limit=index_limit,
        heatmap_limit=heatmap_limit,
        macro_limit=macro_limit,
        futures_limit=futures_limit,
        news_limit=news_limit,
    )


@router.get(
    "/dashboard/stats-overview",
    response_model=DashboardStatsOverviewOut,
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def get_dashboard_stats_overview_route(
    symbol: str | None = Query(None),
    symbols: list[str] | None = Query(None),
    event_type: str | None = Query(None, alias="type"),
    event_types: list[str] | None = Query(None),
    sentiment: str | None = Query(None),
    sentiments: list[str] | None = Query(None),
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    top_date: int | None = Query(None, ge=1, le=365),
    top_type: int | None = Query(None, ge=1, le=1000),
    top_sentiment: int | None = Query(None, ge=1, le=100),
    top_symbol: int | None = Query(None, ge=1, le=2000),
    start: date | None = Query(None),
    end: date | None = Query(None),
    db: Session = Depends(get_db),
):
    symbols_filter = symbols or ([symbol] if symbol else None)
    event_types_filter = event_types or ([event_type] if event_type else None)
    sentiments_filter = sentiments or ([sentiment] if sentiment else None)
    return get_dashboard_stats_overview(
        db,
        symbols=symbols_filter,
        event_types=event_types_filter,
        sentiments=sentiments_filter,
        start=start,
        end=end,
        granularity=granularity,
        top_date=top_date,
        top_type=top_type,
        top_sentiment=top_sentiment,
        top_symbol=top_symbol,
    )
