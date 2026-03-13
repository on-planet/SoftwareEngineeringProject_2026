from __future__ import annotations

from datetime import date as DateType

from pydantic import BaseModel


class RiskOut(BaseModel):
    symbol: str
    max_drawdown: float | None = None
    volatility: float | None = None
    as_of: DateType | None = None
    cache_hit: bool | None = None
