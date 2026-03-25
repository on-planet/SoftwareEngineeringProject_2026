from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.models.base import Base


class BondMarketTrade(Base):
    __tablename__ = "bond_market_trades"

    id = Column(Integer, primary_key=True, index=True)
    bond_name = Column(String(128), index=True)
    deal_net_price = Column(Float)
    latest_yield = Column(Float)
    change = Column(Float)
    weighted_yield = Column(Float)
    volume = Column(Float)
    as_of = Column(DateTime, index=True)
    source = Column(String(64))
    raw_json = Column(Text)
