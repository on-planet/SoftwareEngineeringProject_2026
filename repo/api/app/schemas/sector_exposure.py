from __future__ import annotations

from pydantic import BaseModel


class SectorExposureItemOut(BaseModel):
    sector: str
    value: float
    weight: float


class SectorExposureOut(BaseModel):
    market: str | None = None
    items: list[SectorExposureItemOut]
