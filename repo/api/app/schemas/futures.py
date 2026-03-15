from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class FuturesOut(BaseModel):
    symbol: str
    name: str | None = None
    date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    source: str | None = None

    class Config:
        from_attributes = True


class FuturesPoint(BaseModel):
    date: date
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: float | None = None
    source: str | None = None


class FuturesSeriesOut(BaseModel):
    symbol: str
    items: list[FuturesPoint]
