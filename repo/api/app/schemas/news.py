from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NewsOut(BaseModel):
    id: int
    symbol: str
    title: str
    sentiment: str
    published_at: datetime
    link: str | None = None
    source: str | None = None

    class Config:
        from_attributes = True


class NewsCreate(BaseModel):
    symbol: str
    title: str
    sentiment: str
    published_at: datetime
    link: str | None = None
    source: str | None = None


class NewsUpdate(BaseModel):
    title: str | None = None
    sentiment: str | None = None
    published_at: datetime | None = None
    link: str | None = None
    source: str | None = None
