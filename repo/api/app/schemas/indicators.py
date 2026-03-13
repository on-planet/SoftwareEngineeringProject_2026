from __future__ import annotations

from datetime import date as DateType

from pydantic import BaseModel


class IndicatorPoint(BaseModel):
    date: DateType
    value: float


class IndicatorSeriesOut(BaseModel):
    symbol: str
    indicator: str
    window: int
    items: list[IndicatorPoint]
    cache_hit: bool | None = None


class IndicatorRequest(BaseModel):
    symbol: str
    indicator: str
    window: int = 14
    limit: int = 200
    end: DateType | None = None
