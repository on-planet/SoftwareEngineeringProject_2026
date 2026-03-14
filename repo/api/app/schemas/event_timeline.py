from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class EventTimelineItem(BaseModel):
    symbol: str
    type: str
    title: str
    date: date
    link: str | None = None
    source: str | None = None


class EventTimelineOut(BaseModel):
    items: list[EventTimelineItem]
    total: int
    limit: int
    offset: int
