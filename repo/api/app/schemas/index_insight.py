from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class IndexInsightConstituentOut(BaseModel):
    index_symbol: str
    symbol: str
    date: dt.date | None = None
    weight: float | None = None
    name: str | None = None
    market: str | None = None
    sector: str | None = None
    rank: int | None = None
    current: float | None = None
    change: float | None = None
    percent: float | None = None
    contribution_change: float | None = None
    contribution_score: float | None = None
    source: str | None = None

    class Config:
        from_attributes = True


class IndexInsightSectorOut(BaseModel):
    sector: str
    weight: float
    symbol_count: int
    avg_percent: float | None = None
    leader_symbol: str | None = None
    leader_name: str | None = None


class IndexInsightSummaryOut(BaseModel):
    symbol: str
    name: str
    market: str
    as_of: dt.date | None = None
    constituent_total: int
    priced_total: int
    weight_coverage: float
    top5_weight: float
    top10_weight: float
    rising_count: int
    falling_count: int
    flat_count: int


class IndexInsightOut(BaseModel):
    summary: IndexInsightSummaryOut
    top_weights: list[IndexInsightConstituentOut]
    top_contributors: list[IndexInsightConstituentOut]
    top_detractors: list[IndexInsightConstituentOut]
    sector_breakdown: list[IndexInsightSectorOut]
    constituents: list[IndexInsightConstituentOut]
