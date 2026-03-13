from __future__ import annotations

from sqlalchemy import Column, Date, Float, String

from app.models.base import Base


class DailyPrice(Base):
    __tablename__ = "daily_prices"

    symbol = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
