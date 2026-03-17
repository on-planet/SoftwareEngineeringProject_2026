from __future__ import annotations

from datetime import date as DateType

from pydantic import BaseModel, Field


class IndicatorPoint(BaseModel):
    date: DateType
    value: float | None = None
    values: dict[str, float] = Field(default_factory=dict)


class IndicatorSeriesOut(BaseModel):
    symbol: str
    indicator: str
    window: int
    lines: list[str] = Field(default_factory=list)
    params: dict[str, int | float | str] = Field(default_factory=dict)
    items: list[IndicatorPoint]
    cache_hit: bool | None = None


class IndicatorRequest(BaseModel):
    symbol: str
    indicator: str
    window: int = 14
    limit: int = 200
    end: DateType | None = None
