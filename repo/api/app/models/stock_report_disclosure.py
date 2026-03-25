from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, Integer, String, Text

from app.models.base import Base


class StockReportDisclosure(Base):
    __tablename__ = "stock_report_disclosures"

    id = Column(Integer, primary_key=True, index=True)
    market = Column(String(32), index=True)
    period = Column(String(32), index=True)
    symbol = Column(String(32), index=True)
    stock_name = Column(String(128), index=True)
    first_booking = Column(Date)
    first_change = Column(Date)
    second_change = Column(Date)
    third_change = Column(Date)
    actual_disclosure = Column(Date)
    as_of = Column(DateTime, index=True)
    source = Column(String(64))
    raw_json = Column(Text)
