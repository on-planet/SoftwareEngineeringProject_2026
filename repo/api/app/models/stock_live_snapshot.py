from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, String, Text

from app.models.base import Base


class StockLiveSnapshot(Base):
    __tablename__ = "stock_live_snapshots"

    symbol = Column(String, primary_key=True)
    as_of = Column(DateTime)
    current = Column(Float)
    change = Column(Float)
    percent = Column(Float)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    last_close = Column(Float)
    volume = Column(Float)
    amount = Column(Float)
    turnover_rate = Column(Float)
    amplitude = Column(Float)
    quote_timestamp = Column(DateTime)
    pe_ttm = Column(Float)
    pb = Column(Float)
    ps_ttm = Column(Float)
    pcf = Column(Float)
    market_cap = Column(Float)
    float_market_cap = Column(Float)
    dividend_yield = Column(Float)
    volume_ratio = Column(Float)
    lot_size = Column(Float)
    pankou_diff = Column(Float)
    pankou_ratio = Column(Float)
    pankou_timestamp = Column(DateTime)
    pankou_bids_json = Column(Text)
    pankou_asks_json = Column(Text)
    source = Column(String)
