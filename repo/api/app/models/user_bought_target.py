from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Column, Date, DateTime, Float, Integer, String

from app.models.base import Base


class UserBoughtTarget(Base):
    __tablename__ = "user_bought_targets"

    user_id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(32), primary_key=True)
    buy_price = Column(Float, nullable=False)
    lots = Column(Float, nullable=False)
    buy_date = Column(Date, nullable=False, default=date.today)
    fee = Column(Float, nullable=False, default=0)
    note = Column(String(512), nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
