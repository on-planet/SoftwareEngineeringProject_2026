from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Column, Date, DateTime, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class StockStrategyRun(Base):
    __tablename__ = "stock_strategy_runs"

    id = Column(Integer, primary_key=True, index=True)
    strategy_code = Column(String(64), nullable=False, index=True)
    strategy_name = Column(String(128), nullable=False)
    as_of = Column(Date, nullable=False, index=True)
    label_horizon = Column(Integer, nullable=False, default=60)
    status = Column(String(32), nullable=False, default="ready")
    model_path = Column(Text)
    train_rows = Column(Integer, nullable=False, default=0)
    scored_rows = Column(Integer, nullable=False, default=0)
    evaluation_json = Column(Text, nullable=False, default="{}")
    leaderboard_json = Column(Text, nullable=False, default="[]")
    feature_importance_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    scores = relationship(
        "StockStrategyScore",
        back_populates="run",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="StockStrategyScore.rank.asc(), StockStrategyScore.symbol.asc()",
    )
