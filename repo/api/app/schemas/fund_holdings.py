from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class FundHoldingOut(BaseModel):
    fund_code: str
    symbol: str
    report_date: date
    shares: float | None = None
    market_value: float | None = None
    weight: float | None = None

    class Config:
        from_attributes = True


class FundHoldingCreate(BaseModel):
    fund_code: str
    symbol: str
    report_date: date
    shares: float | None = None
    market_value: float | None = None
    weight: float | None = None


class FundHoldingUpdate(BaseModel):
    shares: float | None = None
    market_value: float | None = None
    weight: float | None = None
