from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE
from app.schemas.event_timeline import EventTimelineOut
from app.services.event_timeline_service import list_event_timeline
from app.utils.query_params import pagination_params, sort_params

router = APIRouter(tags=["events"])


@router.get(
    "/events/timeline",
    response_model=EventTimelineOut,
    responses={
        200: {"content": {"application/json": {"example": {"items": [{"symbol": "000001.SH", "type": "earnings", "title": "2025Q4 业绩预告", "date": "2026-03-10"}], "total": 1, "limit": 20, "offset": 0}}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def get_events_timeline(
    symbol: str | None = Query(None),
    symbols: list[str] | None = Query(None),
    event_type: str | None = Query(None, alias="type"),
    event_types: list[str] | None = Query(None),
    keyword: str | None = Query(None),
    sort_by: list[str] | None = Query(None),
    start: date | None = Query(None),
    end: date | None = Query(None),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    """获取事件时间线。"""
    symbols_filter = symbols or ([symbol] if symbol else None)
    types_filter = event_types or ([event_type] if event_type else None)
    items, total = list_event_timeline(
        db,
        symbols=symbols_filter,
        start=start,
        end=end,
        event_types=types_filter,
        keyword=keyword,
        sort_by=sort_by,
        limit=paging["limit"],
        offset=paging["offset"],
        sort=sorting["sort"],
    )
    return {"items": items, "total": total, **paging}
