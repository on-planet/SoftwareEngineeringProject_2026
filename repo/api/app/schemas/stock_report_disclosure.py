from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class StockReportDisclosureOut(BaseModel):
    market: str
    period: str
    symbol: str
    stock_name: str | None = None
    first_booking: date | None = None
    first_change: date | None = None
    second_change: date | None = None
    third_change: date | None = None
    actual_disclosure: date | None = None
    as_of: datetime | None = None
    source: str | None = None
    payload: dict[str, Any] | None = None
