from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class IndexConstituentOut(BaseModel):
    index_symbol: str
    symbol: str
    date: date
    weight: float

    class Config:
        from_attributes = True
