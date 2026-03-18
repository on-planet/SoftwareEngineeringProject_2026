from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.models.base import Base


class UserWatchTarget(Base):
    __tablename__ = "user_watch_targets"

    user_id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(32), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
