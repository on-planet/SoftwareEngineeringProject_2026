from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class FundHoldingSeriesPoint(BaseModel):
    report_date: date
    total_market_value: float
    total_weight: float
    holdings_count: int


class StockHoldingSeriesPoint(BaseModel):
    report_date: date
    total_market_value: float
    total_weight: float
    fund_count: int


class FundHoldingSeriesOut(BaseModel):
    fund_code: str
    items: list[FundHoldingSeriesPoint]


class StockHoldingSeriesOut(BaseModel):
    symbol: str
    items: list[StockHoldingSeriesPoint]
