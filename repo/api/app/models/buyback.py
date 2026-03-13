from __future__ import annotations

from sqlalchemy import Column, Date, Float, String

from app.models.base import Base


class Buyback(Base):
    __tablename__ = "buyback"

    symbol = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    amount = Column(Float)
