from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class KlinePoint(BaseModel):
    date: date
    open: float
    high: float
    low: float
    close: float


class KlineSeriesOut(BaseModel):
    symbol: str
    items: list[KlinePoint]
