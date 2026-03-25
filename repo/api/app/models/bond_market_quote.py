from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.models.base import Base


class BondMarketQuote(Base):
    __tablename__ = "bond_market_quotes"

    id = Column(Integer, primary_key=True, index=True)
    quote_org = Column(String(128), index=True)
    bond_name = Column(String(128), index=True)
    buy_net_price = Column(Float)
    sell_net_price = Column(Float)
    buy_yield = Column(Float)
    sell_yield = Column(Float)
    as_of = Column(DateTime, index=True)
    source = Column(String(64))
    raw_json = Column(Text)
