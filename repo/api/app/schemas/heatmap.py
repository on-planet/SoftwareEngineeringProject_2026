from __future__ import annotations

from pydantic import BaseModel


class HeatmapItemOut(BaseModel):
    sector: str
    avg_close: float
    avg_change: float
