from __future__ import annotations

from sqlalchemy import Column, Float, String

from app.models.base import Base


class SectorExposure(Base):
    __tablename__ = "sector_exposure"

    sector = Column(String, primary_key=True)
    market = Column(String, primary_key=True)
    value = Column(Float)
