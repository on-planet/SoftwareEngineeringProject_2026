from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.error import ErrorResponse
from app.schemas.event_stats import EventStatsOut
from app.schemas.examples import ERROR_EXAMPLE
from app.services.event_stats_service import get_event_stats

router = APIRouter(tags=["events"])


@router.get(
    "/events/stats",
    response_model=EventStatsOut,
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def get_events_stats(
    symbol: str | None = Query(None),
    symbols: list[str] | None = Query(None),
    event_type: str | None = Query(None, alias="type"),
    event_types: list[str] | None = Query(None),
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    top_date: int | None = Query(None, ge=1, le=365),
    top_type: int | None = Query(None, ge=1, le=1000),
    top_symbol: int | None = Query(None, ge=1, le=2000),
    start: date | None = Query(None),
    end: date | None = Query(None),
    db: Session = Depends(get_db),
):
    """获取事件统计（按日/类型/标的）。"""
    symbols_filter = symbols or ([symbol] if symbol else None)
    types_filter = event_types or ([event_type] if event_type else None)
    by_date, by_type, by_symbol, cache_meta = get_event_stats(
        db,
        symbols=symbols_filter,
        event_types=types_filter,
        start=start,
        end=end,
        granularity=granularity,
        top_date=top_date,
        top_type=top_type,
        top_symbol=top_symbol,
        return_meta=True,
    )
    return {"by_date": by_date, "by_type": by_type, "by_symbol": by_symbol, **cache_meta}
