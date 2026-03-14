from __future__ import annotations

from datetime import date as DateType

from pydantic import BaseModel


class EventOut(BaseModel):
    id: int
    symbol: str
    type: str
    title: str
    date: DateType
    link: str | None = None
    source: str | None = None

    class Config:
        from_attributes = True


class EventCreate(BaseModel):
    symbol: str
    type: str
    title: str
    date: DateType
    link: str | None = None
    source: str | None = None


class EventUpdate(BaseModel):
    type: str | None = None
    title: str | None = None
    date: DateType | None = None
    link: str | None = None
    source: str | None = None
