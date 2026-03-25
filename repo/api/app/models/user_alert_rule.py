from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String

from app.models.base import Base


class UserAlertRule(Base):
    __tablename__ = "user_alert_rules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    rule_type = Column(String(32), nullable=False, index=True)
    symbol = Column(String(32), nullable=False, index=True)
    price_operator = Column(String(8), nullable=True)
    threshold = Column(Float, nullable=True)
    event_type = Column(String(64), nullable=True)
    research_kind = Column(String(32), nullable=True)
    lookback_days = Column(Integer, nullable=False, default=7)
    is_active = Column(Boolean, nullable=False, default=True)
    note = Column(String(512), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
