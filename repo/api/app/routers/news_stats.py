from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE
from app.schemas.news_stats import NewsStatsOut
from app.services.news_stats_service import get_news_stats as fetch_news_stats

router = APIRouter(tags=["news"])


@router.get(
    "/news/stats",
    response_model=NewsStatsOut,
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def get_news_stats_route(
    symbol: str | None = Query(None),
    symbols: list[str] | None = Query(None),
    sentiment: str | None = Query(None),
    sentiments: list[str] | None = Query(None),
    granularity: str = Query("day", pattern="^(day|week|month)$"),
    top_date: int | None = Query(None, ge=1, le=365),
    top_sentiment: int | None = Query(None, ge=1, le=100),
    top_symbol: int | None = Query(None, ge=1, le=2000),
    start: date | None = Query(None),
    end: date | None = Query(None),
    db: Session = Depends(get_db),
):
    """获取新闻统计（按日/情绪/标的）。"""
    symbols_filter = symbols or ([symbol] if symbol else None)
    sentiments_filter = sentiments or ([sentiment] if sentiment else None)
    by_date, by_sentiment, by_symbol = fetch_news_stats(
        db,
        symbols=symbols_filter,
        sentiments=sentiments_filter,
        start=start,
        end=end,
        granularity=granularity,
        top_date=top_date,
        top_sentiment=top_sentiment,
        top_symbol=top_symbol,
    )
    return {"by_date": by_date, "by_sentiment": by_sentiment, "by_symbol": by_symbol}
