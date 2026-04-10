from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, Date, DateTime, Float, Integer, String

from app.models.base import Base


class StockFactorExposureCache(Base):
    __tablename__ = "stock_factor_exposure_cache"

    symbol = Column(String(32), primary_key=True)
    as_of = Column(Date, primary_key=True)
    market = Column(String(16), nullable=False, default="")
    sector = Column(String(64), nullable=False, default="")
    market_beta = Column(Float, nullable=False, default=0.0)
    sector_beta = Column(Float, nullable=False, default=0.0)
    rate_beta = Column(Float, nullable=False, default=0.0)
    fx_beta = Column(Float, nullable=False, default=0.0)
    commodity_beta = Column(Float, nullable=False, default=0.0)
    idiosyncratic_term = Column(Float, nullable=False, default=0.0)
    sample_size = Column(Integer, nullable=False, default=0)
    window_size = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
