from __future__ import annotations

from sqlalchemy import Column, Date, Float, String

from app.models.base import Base


class Macro(Base):
    __tablename__ = "macro"

    key = Column(String, primary_key=True)
    date = Column(Date, primary_key=True)
    value = Column(Float)
    score = Column(Float)
