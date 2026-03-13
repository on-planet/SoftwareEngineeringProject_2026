from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.events import Event
from app.schemas.events import EventCreate, EventUpdate
from app.utils.query_params import SortOrder


def list_events(
    db: Session,
    symbol: str,
    limit: int = 50,
    offset: int = 0,
    start: date | None = None,
    end: date | None = None,
    event_types: list[str] | None = None,
    keyword: str | None = None,
    sort_by: list[str] | None = None,
    sort: SortOrder = "desc",
):
    """List events by symbol."""
    query = db.query(Event).filter(Event.symbol == symbol)
    if event_types:
        query = query.filter(Event.type.in_(event_types))
    if keyword:
        keyword_like = f"%{keyword}%"
        query = query.filter(Event.title.ilike(keyword_like))
    if start is not None:
        query = query.filter(Event.date >= start)
    if end is not None:
        query = query.filter(Event.date <= end)
    total = query.count()
    sort_fields = {
        "date": Event.date,
        "title": Event.title,
        "type": Event.type,
    }
    sort_keys = [key for key in (sort_by or ["date"]) if key in sort_fields]
    if not sort_keys:
        sort_keys = ["date"]
    ordering = [
        (sort_fields[key].asc() if sort == "asc" else sort_fields[key].desc())
        for key in sort_keys
    ]
    items = (
        query.order_by(*ordering)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return items, total


def create_event(db: Session, payload: EventCreate):
    item = Event(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_event(db: Session, event_id: int, payload: EventUpdate):
    item = db.query(Event).filter(Event.id == event_id).first()
    if item is None:
        return None
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_event(db: Session, event_id: int) -> bool:
    item = db.query(Event).filter(Event.id == event_id).first()
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
