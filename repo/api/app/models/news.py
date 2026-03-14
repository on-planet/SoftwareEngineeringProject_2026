from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String

from app.models.base import Base


class News(Base):
    __tablename__ = "news"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    title = Column(String)
    sentiment = Column(String)
    published_at = Column(DateTime)
    link = Column(String)
    source = Column(String)
