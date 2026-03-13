from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class FundHoldingFundStat(BaseModel):
    fund_code: str
    report_date: date
    total_market_value: float
    total_weight: float
    holdings_count: int


class FundHoldingStockStat(BaseModel):
    symbol: str
    report_date: date
    total_market_value: float
    total_weight: float
    fund_count: int
