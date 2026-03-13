from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class CountByDateItem(BaseModel):
    date: date
    count: int


class CountByTypeItem(BaseModel):
    type: str
    count: int


class CountBySymbolItem(BaseModel):
    symbol: str
    count: int


class EventStatsOut(BaseModel):
    by_date: list[CountByDateItem]
    by_type: list[CountByTypeItem]
    by_symbol: list[CountBySymbolItem]
