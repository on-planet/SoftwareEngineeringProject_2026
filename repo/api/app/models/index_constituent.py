from __future__ import annotations

from sqlalchemy import Column, Date, Float, String

from app.models.base import Base


class IndexConstituent(Base):
    __tablename__ = "index_constituents"

    index_symbol = Column(String, primary_key=True)
    symbol = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    weight = Column(Float)
