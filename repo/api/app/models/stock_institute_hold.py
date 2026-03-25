from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, Integer, String, Text

from app.models.base import Base


class StockInstituteHold(Base):
    __tablename__ = "stock_institute_holds"

    id = Column(Integer, primary_key=True, index=True)
    quarter = Column(String(16), index=True)
    symbol = Column(String(32), index=True)
    stock_name = Column(String(128), index=True)
    institute_count = Column(Float)
    institute_count_change = Column(Float)
    holding_ratio = Column(Float)
    holding_ratio_change = Column(Float)
    float_holding_ratio = Column(Float)
    float_holding_ratio_change = Column(Float)
    as_of = Column(DateTime, index=True)
    source = Column(String(64))
    raw_json = Column(Text)


class StockInstituteHoldDetail(Base):
    __tablename__ = "stock_institute_hold_details"

    id = Column(Integer, primary_key=True, index=True)
    quarter = Column(String(16), index=True)
    stock_symbol = Column(String(32), index=True)
    institute_type = Column(String(64), index=True)
    institute_code = Column(String(64), index=True)
    institute_name = Column(String(128), index=True)
    institute_full_name = Column(String(255))
    shares = Column(Float)
    latest_shares = Column(Float)
    holding_ratio = Column(Float)
    latest_holding_ratio = Column(Float)
    float_holding_ratio = Column(Float)
    latest_float_holding_ratio = Column(Float)
    holding_ratio_change = Column(Float)
    float_holding_ratio_change = Column(Float)
    as_of = Column(DateTime, index=True)
    source = Column(String(64))
    raw_json = Column(Text)
