from __future__ import annotations

from sqlalchemy import Column, Date, Integer, String

from app.models.base import Base


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    type = Column(String)
    title = Column(String)
    date = Column(Date)
