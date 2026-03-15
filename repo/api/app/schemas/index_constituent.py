from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class IndexConstituentOut(BaseModel):
    index_symbol: str
    symbol: str
    date: date
    weight: float | None = None
    name: str | None = None
    market: str | None = None
    rank: int | None = None
    contribution_change: float | None = None
    source: str | None = None

    class Config:
        from_attributes = True
