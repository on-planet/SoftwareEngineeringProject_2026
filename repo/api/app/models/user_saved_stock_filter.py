from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String

from app.models.base import Base


class UserSavedStockFilter(Base):
    __tablename__ = "user_saved_stock_filters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    market = Column(String(16), nullable=False, default="A")
    keyword = Column(String(128), nullable=False, default="")
    sector = Column(String(128), nullable=False, default="")
    sort = Column(String(8), nullable=False, default="asc")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
