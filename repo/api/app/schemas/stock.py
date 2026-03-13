from __future__ import annotations

from datetime import date as DateType

from pydantic import BaseModel, Field

from app.schemas.risk import RiskOut


class StockOut(BaseModel):
    symbol: str
    name: str
    market: str
    sector: str

    class Config:
        from_attributes = True


class DailyPriceOut(BaseModel):
    symbol: str
    date: DateType
    open: float
    high: float
    low: float
    close: float
    volume: float

    class Config:
        from_attributes = True


class StockCreate(BaseModel):
    symbol: str
    name: str
    market: str
    sector: str


class StockUpdate(BaseModel):
    name: str | None = None
    market: str | None = None
    sector: str | None = None


class StockWithRiskOut(BaseModel):
    symbol: str
    name: str
    market: str
    sector: str
    risk: RiskOut | None = None

    class Config:
        from_attributes = True
