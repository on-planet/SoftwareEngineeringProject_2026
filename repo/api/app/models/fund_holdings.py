from __future__ import annotations

from sqlalchemy import Column, Date, Float, String

from app.models.base import Base


class FundHolding(Base):
    __tablename__ = "fund_holdings"

    fund_code = Column(String, primary_key=True)
    symbol = Column(String, primary_key=True)
    report_date = Column(Date, primary_key=True)
    shares = Column(Float)
    market_value = Column(Float)
    weight = Column(Float)
