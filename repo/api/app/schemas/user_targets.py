from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class WatchTargetCreateIn(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)


class WatchTargetBatchUpsertIn(BaseModel):
    symbols: list[str] = Field(default_factory=list)


class WatchTargetOut(BaseModel):
    symbol: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class BoughtTargetUpsertIn(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    buy_price: float = Field(..., gt=0)
    lots: float = Field(..., gt=0)
    buy_date: date
    fee: float = Field(0, ge=0)
    note: str = Field("", max_length=512)


class BoughtTargetBatchUpsertIn(BaseModel):
    items: list[BoughtTargetUpsertIn] = Field(default_factory=list)


class BoughtTargetOut(BaseModel):
    symbol: str
    buy_price: float
    lots: float
    buy_date: date
    fee: float
    note: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
