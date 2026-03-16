from __future__ import annotations

from sqlalchemy import Column, Date, Float, String

from app.models.base import Base


class StockValuationSnapshot(Base):
    __tablename__ = "stock_valuation_snapshots"

    symbol = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    market_cap = Column(Float)
    float_market_cap = Column(Float)
    source = Column(String)
