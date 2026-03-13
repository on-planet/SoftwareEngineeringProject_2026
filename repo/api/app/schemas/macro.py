from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class MacroOut(BaseModel):
    key: str
    date: date
    value: float
    score: float | None = None

    class Config:
        from_attributes = True


class MacroCreate(BaseModel):
    key: str
    date: date
    value: float
    score: float | None = None


class MacroUpdate(BaseModel):
    value: float | None = Field(None, ge=0)
    score: float | None = Field(None, ge=0)
