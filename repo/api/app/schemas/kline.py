from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


KlinePeriod = Literal["1m", "30m", "60m", "day", "week", "month", "quarter", "year"]


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


class KlineCompareSeriesIn(BaseModel):
    symbol: str
    kind: Literal["stock", "index"] = "stock"
    start: date | None = None
    end: date | None = None


class KlineCompareIn(BaseModel):
    period: KlinePeriod = "day"
    limit: int = 200
    series: list[KlineCompareSeriesIn]


class KlineCompareSeriesOut(BaseModel):
    symbol: str
    kind: Literal["stock", "index"]
    period: str
    items: list[KlinePoint]
    error: str | None = None


class KlineCompareOut(BaseModel):
    period: str
    limit: int
    series: list[KlineCompareSeriesOut]
