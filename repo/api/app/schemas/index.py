from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class IndexOut(BaseModel):
    symbol: str
    name: str | None = None
    market: str | None = None
    date: date
    close: float
    change: float

    class Config:
        from_attributes = True


class IndexCreate(BaseModel):
    symbol: str
    date: date
    close: float
    change: float


class IndexUpdate(BaseModel):
    close: float | None = Field(None, ge=0)
    change: float | None = None
