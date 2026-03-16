from __future__ import annotations

from sqlalchemy import Column, Date, Float, String

from app.models.base import Base


class FuturesWeeklyPrice(Base):
    __tablename__ = "futures_weekly_prices"

    symbol = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    name = Column(String)
    contract_month = Column(String)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    settlement = Column(Float)
    open_interest = Column(Float)
    turnover = Column(Float)
    volume = Column(Float)
    source = Column(String)
