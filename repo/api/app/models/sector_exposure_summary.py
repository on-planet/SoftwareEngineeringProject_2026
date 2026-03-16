from __future__ import annotations

from sqlalchemy import Column, Date, Float, Integer, String

from app.models.base import Base


class SectorExposureSummary(Base):
    __tablename__ = "sector_exposure_summary"

    date = Column(Date, primary_key=True)
    market = Column(String, primary_key=True)
    basis = Column(String, primary_key=True)
    total_value = Column(Float)
    total_symbol_count = Column(Integer)
    covered_symbol_count = Column(Integer)
    classified_symbol_count = Column(Integer)
    unknown_symbol_count = Column(Integer)
    unknown_value = Column(Float)
    coverage = Column(Float)
