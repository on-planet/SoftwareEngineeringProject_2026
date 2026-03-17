from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, String

from app.models.base import Base


class StockIntradayKline(Base):
    __tablename__ = "stock_intraday_kline"

    symbol = Column(String, primary_key=True)
    period = Column(String, primary_key=True)
    timestamp = Column(DateTime, primary_key=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
