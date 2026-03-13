from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class RiskPoint(BaseModel):
    date: date
    max_drawdown: float
    volatility: float


class RiskSeriesOut(BaseModel):
    symbol: str
    items: list[RiskPoint]
    cache_hit: bool | None = None
