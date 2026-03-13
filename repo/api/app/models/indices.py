from __future__ import annotations

from sqlalchemy import Column, Date, Float, String

from app.models.base import Base


class Index(Base):
    __tablename__ = "indices"

    symbol = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    close = Column(Float)
    change = Column(Float)
