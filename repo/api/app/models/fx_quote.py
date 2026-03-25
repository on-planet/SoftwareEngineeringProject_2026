from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.models.base import Base


class FxSpotQuote(Base):
    __tablename__ = "fx_spot_quotes"

    id = Column(Integer, primary_key=True, index=True)
    currency_pair = Column(String(32), index=True)
    bid = Column(Float)
    ask = Column(Float)
    as_of = Column(DateTime, index=True)
    source = Column(String(64))
    raw_json = Column(Text)


class FxSwapQuote(Base):
    __tablename__ = "fx_swap_quotes"

    id = Column(Integer, primary_key=True, index=True)
    currency_pair = Column(String(32), index=True)
    one_week = Column(Float)
    one_month = Column(Float)
    three_month = Column(Float)
    six_month = Column(Float)
    nine_month = Column(Float)
    one_year = Column(Float)
    as_of = Column(DateTime, index=True)
    source = Column(String(64))
    raw_json = Column(Text)


class FxPairQuote(Base):
    __tablename__ = "fx_pair_quotes"

    id = Column(Integer, primary_key=True, index=True)
    currency_pair = Column(String(32), index=True)
    bid = Column(Float)
    ask = Column(Float)
    as_of = Column(DateTime, index=True)
    source = Column(String(64))
    raw_json = Column(Text)
