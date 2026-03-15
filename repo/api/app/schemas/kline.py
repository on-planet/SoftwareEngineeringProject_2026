from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel


class KlinePoint(BaseModel):
    date: datetime | date
    open: float
    high: float
    low: float
    close: float


class KlineSeriesOut(BaseModel):
    symbol: str
    period: str
    items: list[KlinePoint]
