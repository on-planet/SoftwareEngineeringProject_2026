from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class NewsCountByDateItem(BaseModel):
    date: date
    count: int


class NewsCountBySentimentItem(BaseModel):
    sentiment: str
    count: int


class NewsCountBySymbolItem(BaseModel):
    symbol: str
    count: int


class NewsStatsOut(BaseModel):
    by_date: list[NewsCountByDateItem]
    by_sentiment: list[NewsCountBySentimentItem]
    by_symbol: list[NewsCountBySymbolItem]
