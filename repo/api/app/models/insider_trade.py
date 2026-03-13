from __future__ import annotations

from sqlalchemy import Column, Date, Float, Integer, String

from app.models.base import Base


class InsiderTrade(Base):
    __tablename__ = "insider_trade"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    date = Column(Date)
    type = Column(String)
    shares = Column(Float)
