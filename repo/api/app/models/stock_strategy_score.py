from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class StockStrategyScore(Base):
    __tablename__ = "stock_strategy_scores"

    run_id = Column(Integer, ForeignKey("stock_strategy_runs.id", ondelete="CASCADE"), primary_key=True)
    symbol = Column(String(32), primary_key=True, index=True)
    as_of = Column(Date, nullable=False, index=True)
    score = Column(Float, nullable=False)
    rank = Column(Integer, nullable=False, index=True)
    percentile = Column(Float, nullable=False)
    expected_return = Column(Float)
    signal = Column(String(32), nullable=False, default="watch", index=True)
    summary = Column(Text)
    feature_values_json = Column(Text, nullable=False, default="{}")
    driver_factors_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, nullable=False, default=_utcnow)

    run = relationship("StockStrategyRun", back_populates="scores")
