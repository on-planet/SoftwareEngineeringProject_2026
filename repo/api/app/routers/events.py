from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.common import IdOut
from app.schemas.events import EventOut, EventCreate, EventUpdate
from app.schemas.pagination import Page
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE
from app.services.events_service import list_events, create_event, update_event, delete_event
from app.utils.query_params import pagination_params, sort_params

router = APIRouter(tags=["events"])


@router.get(
    "/stock/{symbol}/events",
    response_model=Page[EventOut],
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def list_events_route(
    symbol: str,
    start: date | None = Query(None),
    end: date | None = Query(None),
    event_type: str | None = Query(None, alias="type"),
    event_types: list[str] | None = Query(None),
    keyword: str | None = Query(None),
    sort_by: list[str] | None = Query(None),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    """获取事件列表。"""
    types_filter = event_types or ([event_type] if event_type else None)
    items, total = list_events(
        db,
        symbol,
        limit=paging["limit"],
        offset=paging["offset"],
        start=start,
        end=end,
        event_types=types_filter,
        keyword=keyword,
        sort_by=sort_by,
        sort=sorting["sort"],
    )
    return {"items": items, "total": total, **paging}


@router.post(
    "/events",
    response_model=EventOut,
    responses={400: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def create_event_route(payload: EventCreate, db: Session = Depends(get_db)):
    """创建事件记录。"""
    return create_event(db, payload)


@router.patch(
    "/events/{event_id}",
    response_model=EventOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def update_event_route(event_id: int, payload: EventUpdate, db: Session = Depends(get_db)):
    """更新事件记录。"""
    item = update_event(db, event_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return item


@router.delete(
    "/events/{event_id}",
    response_model=IdOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def delete_event_route(event_id: int, db: Session = Depends(get_db)):
    """删除事件记录。"""
    ok = delete_event(db, event_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"id": event_id}
