from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, String, Text

from app.models.base import Base


class StockResearchItem(Base):
    __tablename__ = "stock_research_items"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, index=True)
    item_type = Column(String, index=True)
    title = Column(String)
    published_at = Column(DateTime)
    link = Column(String)
    summary = Column(Text)
    institution = Column(String)
    rating = Column(String)
    source = Column(String)
