from __future__ import annotations

from datetime import date as DateType
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.fundamental import FundamentalOut
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


class StockQuoteOut(BaseModel):
    current: float | None = None
    change: float | None = None
    percent: float | None = None
    open: float | None = None
    high: float | None = None
    low: float | None = None
    last_close: float | None = None
    volume: float | None = None
    amount: float | None = None
    turnover_rate: float | None = None
    amplitude: float | None = None
    timestamp: datetime | None = None


class StockQuoteDetailOut(BaseModel):
    pe_ttm: float | None = None
    pb: float | None = None
    ps_ttm: float | None = None
    pcf: float | None = None
    market_cap: float | None = None
    float_market_cap: float | None = None
    dividend_yield: float | None = None
    volume_ratio: float | None = None
    lot_size: float | None = None


class PankouLevelOut(BaseModel):
    level: int
    price: float | None = None
    volume: float | None = None


class StockPankouOut(BaseModel):
    diff: float | None = None
    ratio: float | None = None
    timestamp: datetime | None = None
    bids: list[PankouLevelOut] = Field(default_factory=list)
    asks: list[PankouLevelOut] = Field(default_factory=list)


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
    quote: StockQuoteOut | None = None
    quote_detail: StockQuoteDetailOut | None = None
    pankou: StockPankouOut | None = None
    risk: RiskOut | None = None

    class Config:
        from_attributes = True


class StockOverviewOut(BaseModel):
    symbol: str
    name: str
    market: str
    sector: str
    quote: StockQuoteOut | None = None
    risk: RiskOut | None = None
    fundamental: FundamentalOut | None = None

    class Config:
        from_attributes = True


class StockExtrasOut(BaseModel):
    symbol: str
    quote_detail: StockQuoteDetailOut | None = None
    pankou: StockPankouOut | None = None


class StockProfilePanelOut(BaseModel):
    symbol: str
    name: str
    market: str
    sector: str
    quote: StockQuoteOut | None = None
    quote_detail: StockQuoteDetailOut | None = None
    pankou: StockPankouOut | None = None
    risk: RiskOut | None = None
    fundamental: FundamentalOut | None = None

    class Config:
        from_attributes = True


class StockCompareBatchIn(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    prefer_live: bool = False


class StockCompareItemOut(BaseModel):
    symbol: str
    name: str
    market: str
    sector: str
    quote: StockQuoteOut | None = None
    error: str | None = None


class StockCompareBatchOut(BaseModel):
    items: list[StockCompareItemOut] = Field(default_factory=list)
