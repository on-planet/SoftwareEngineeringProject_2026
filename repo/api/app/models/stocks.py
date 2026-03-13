from __future__ import annotations

from sqlalchemy import Column, Integer, String

from app.models.base import Base


class Stock(Base):
    __tablename__ = "stocks"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True, unique=True)
    name = Column(String)
    market = Column(String)
    sector = Column(String)
