from __future__ import annotations

from datetime import date as DateType

from pydantic import BaseModel


class FinancialOut(BaseModel):
    symbol: str
    period: str
    revenue: float
    net_income: float
    cash_flow: float
    roe: float
    debt_ratio: float

    class Config:
        from_attributes = True


class FinancialCreate(BaseModel):
    symbol: str
    period: str
    revenue: float
    net_income: float
    cash_flow: float
    roe: float
    debt_ratio: float


class FinancialUpdate(BaseModel):
    revenue: float | None = None
    net_income: float | None = None
    cash_flow: float | None = None
    roe: float | None = None
    debt_ratio: float | None = None
