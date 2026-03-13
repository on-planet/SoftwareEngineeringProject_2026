from __future__ import annotations

from sqlalchemy import Column, Float, String

from app.models.base import Base


class Financial(Base):
    __tablename__ = "financials"

    symbol = Column(String, primary_key=True)
    period = Column(String, primary_key=True)
    revenue = Column(Float)
    net_income = Column(Float)
    cash_flow = Column(Float)
    roe = Column(Float)
    debt_ratio = Column(Float)
