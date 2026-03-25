from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class StockInstituteHoldOut(BaseModel):
    quarter: str
    symbol: str
    stock_name: str | None = None
    institute_count: float | None = None
    institute_count_change: float | None = None
    holding_ratio: float | None = None
    holding_ratio_change: float | None = None
    float_holding_ratio: float | None = None
    float_holding_ratio_change: float | None = None
    as_of: datetime | None = None
    source: str | None = None


class StockInstituteHoldDetailOut(BaseModel):
    quarter: str
    stock_symbol: str
    institute_type: str | None = None
    institute_code: str | None = None
    institute_name: str | None = None
    institute_full_name: str | None = None
    shares: float | None = None
    latest_shares: float | None = None
    holding_ratio: float | None = None
    latest_holding_ratio: float | None = None
    float_holding_ratio: float | None = None
    latest_float_holding_ratio: float | None = None
    holding_ratio_change: float | None = None
    float_holding_ratio_change: float | None = None
    as_of: datetime | None = None
    source: str | None = None
    payload: dict[str, Any] | None = None


class StockInstituteRecommendOut(BaseModel):
    category: str
    symbol: str | None = None
    stock_name: str | None = None
    rating_date: date | None = None
    rating: str | None = None
    metric_name: str | None = None
    metric_value: float | None = None
    extra_text: str | None = None
    as_of: datetime | None = None
    source: str | None = None
    payload: dict[str, Any] | None = None


class StockInstituteRecommendDetailOut(BaseModel):
    symbol: str
    rating_date: date | None = None
    institution: str | None = None
    rating: str | None = None
    previous_rating: str | None = None
    target_price: float | None = None
    title: str | None = None
    as_of: datetime | None = None
    source: str | None = None
    payload: dict[str, Any] | None = None
