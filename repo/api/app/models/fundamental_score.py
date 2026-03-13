from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, String

from app.models.base import Base


class FundamentalScore(Base):
    __tablename__ = "fundamental_score"

    symbol = Column(String, primary_key=True)
    score = Column(Float)
    summary = Column(String)
    updated_at = Column(DateTime)
