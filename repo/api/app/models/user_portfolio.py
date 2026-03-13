from __future__ import annotations

from sqlalchemy import Column, Float, Integer, String

from app.models.base import Base


class UserPortfolio(Base):
    __tablename__ = "user_portfolio"

    user_id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, primary_key=True)
    avg_cost = Column(Float)
    shares = Column(Float)
