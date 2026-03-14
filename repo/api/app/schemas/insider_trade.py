from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class InsiderTradeOut(BaseModel):
    id: int | None = None
    symbol: str
    date: date
    type: str
    shares: float

    class Config:
        from_attributes = True


class InsiderTradeCreate(BaseModel):
    symbol: str
    date: date
    type: str
    shares: float


class InsiderTradeUpdate(BaseModel):
    type: str | None = None
    shares: float | None = None
