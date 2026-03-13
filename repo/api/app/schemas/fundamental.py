from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class FundamentalOut(BaseModel):
    symbol: str
    score: float
    summary: str
    updated_at: datetime

    class Config:
        from_attributes = True


class FundamentalCreate(BaseModel):
    symbol: str
    score: float
    summary: str
    updated_at: datetime


class FundamentalUpdate(BaseModel):
    score: float | None = None
    summary: str | None = None
    updated_at: datetime | None = None
