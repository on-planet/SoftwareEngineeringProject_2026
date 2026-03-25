from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class NewsOut(BaseModel):
    id: int
    symbol: str
    title: str
    sentiment: str
    published_at: datetime
    link: str | None = None
    source: str | None = None
    source_site: str | None = None
    source_category: str | None = None
    topic_category: str | None = None
    time_bucket: str | None = None
    related_symbols: list[str] = Field(default_factory=list)
    related_sectors: list[str] = Field(default_factory=list)

    class Config:
        from_attributes = True


class NewsCreate(BaseModel):
    symbol: str
    title: str
    sentiment: str
    published_at: datetime
    link: str | None = None
    source: str | None = None
    source_site: str | None = None
    source_category: str | None = None
    topic_category: str | None = None
    time_bucket: str | None = None
    related_symbols: list[str] | str | None = None
    related_sectors: list[str] | str | None = None


class NewsUpdate(BaseModel):
    title: str | None = None
    sentiment: str | None = None
    published_at: datetime | None = None
    link: str | None = None
    source: str | None = None
    source_site: str | None = None
    source_category: str | None = None
    topic_category: str | None = None
    time_bucket: str | None = None
    related_symbols: list[str] | str | None = None
    related_sectors: list[str] | str | None = None
