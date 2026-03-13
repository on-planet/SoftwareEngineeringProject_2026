from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class BuybackOut(BaseModel):
    symbol: str
    date: date
    amount: float

    class Config:
        from_attributes = True


class BuybackCreate(BaseModel):
    symbol: str
    date: date
    amount: float


class BuybackUpdate(BaseModel):
    amount: float | None = None
