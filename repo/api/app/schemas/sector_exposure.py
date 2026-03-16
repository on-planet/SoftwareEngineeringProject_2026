from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class SectorExposureItemOut(BaseModel):
    sector: str
    value: float
    weight: float
    symbol_count: int | None = None


class SectorExposureOut(BaseModel):
    market: str | None = None
    as_of: date | None = None
    basis: str = "market_value"
    total_value: float = 0.0
    coverage: float = 0.0
    unknown_weight: float = 0.0
    items: list[SectorExposureItemOut]
