from __future__ import annotations

from sqlalchemy import Column, Date, DateTime, Float, Integer, String, Text

from app.models.base import Base


class StockInstituteRecommend(Base):
    __tablename__ = "stock_institute_recommendations"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(64), index=True)
    symbol = Column(String(32), index=True)
    stock_name = Column(String(128), index=True)
    rating_date = Column(Date, index=True)
    rating = Column(String(64), index=True)
    metric_name = Column(String(64))
    metric_value = Column(Float)
    extra_text = Column(String(255))
    as_of = Column(DateTime, index=True)
    source = Column(String(64))
    raw_json = Column(Text)


class StockInstituteRecommendDetail(Base):
    __tablename__ = "stock_institute_recommendation_details"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(32), index=True)
    rating_date = Column(Date, index=True)
    institution = Column(String(128), index=True)
    rating = Column(String(64), index=True)
    previous_rating = Column(String(64))
    target_price = Column(Float)
    title = Column(String(255))
    as_of = Column(DateTime, index=True)
    source = Column(String(64))
    raw_json = Column(Text)
