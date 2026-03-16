from __future__ import annotations

from sqlalchemy import Column, Date, Float, Integer, String

from app.models.base import Base


class SectorExposure(Base):
    __tablename__ = "sector_exposure_daily"

    date = Column(Date, primary_key=True)
    market = Column(String, primary_key=True)
    basis = Column(String, primary_key=True)
    sector = Column(String, primary_key=True)
    value = Column(Float)
    weight = Column(Float)
    symbol_count = Column(Integer)
