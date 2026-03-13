from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class MacroPoint(BaseModel):
    date: date
    value: float
    score: float | None = None


class MacroSeriesOut(BaseModel):
    key: str
    items: list[MacroPoint]
