from __future__ import annotations

from datetime import date

from sqlalchemy import Date, func
from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.news import News
from app.services.cache_utils import build_cache_key, item_to_dict
from app.schemas.news_stats import (
    NewsCountByDateItem,
    NewsCountBySentimentItem,
    NewsCountBySymbolItem,
)

NEWS_STATS_CACHE_TTL = 600


def _date_bucket(column, granularity: str):
    if granularity == "week":
        return func.date_trunc("week", column).cast(Date)
    if granularity == "month":
        return func.date_trunc("month", column).cast(Date)
    return func.date_trunc("day", column).cast(Date)


def get_news_stats(
    db: Session,
    symbols: list[str] | None = None,
    sentiments: list[str] | None = None,
    start: date | None = None,
    end: date | None = None,
    granularity: str = "day",
    top_date: int | None = None,
    top_sentiment: int | None = None,
    top_symbol: int | None = None,
):
    cache_key = build_cache_key(
        "news:stats",
        symbols=symbols,
        sentiments=sentiments,
        start=start,
        end=end,
        granularity=granularity,
        top_date=top_date,
        top_sentiment=top_sentiment,
        top_symbol=top_symbol,
    )
    cached = get_json(cache_key)
    if isinstance(cached, dict):
        by_date = cached.get("by_date")
        by_sentiment = cached.get("by_sentiment")
        by_symbol = cached.get("by_symbol")
        if isinstance(by_date, list) and isinstance(by_sentiment, list) and isinstance(by_symbol, list):
            return (
                [NewsCountByDateItem(**row) for row in by_date if isinstance(row, dict)],
                [NewsCountBySentimentItem(**row) for row in by_sentiment if isinstance(row, dict)],
                [NewsCountBySymbolItem(**row) for row in by_symbol if isinstance(row, dict)],
            )

    base_query = db.query(News)
    if symbols:
        base_query = base_query.filter(News.symbol.in_(symbols))
    if sentiments:
        base_query = base_query.filter(News.sentiment.in_(sentiments))
    if start is not None:
        base_query = base_query.filter(News.published_at >= start)
    if end is not None:
        base_query = base_query.filter(News.published_at <= end)

    bucket = _date_bucket(News.published_at, granularity)
    by_date_query = base_query.with_entities(
        bucket.label("date"), func.count().label("count")
    ).group_by(bucket)
    if top_date:
        by_date_query = by_date_query.order_by(func.count().desc()).limit(top_date)
    else:
        by_date_query = by_date_query.order_by(bucket.asc())
    by_date_rows = by_date_query.all()

    by_sentiment_query = base_query.with_entities(
        News.sentiment.label("sentiment"), func.count().label("count")
    ).group_by(News.sentiment)
    by_sentiment_query = by_sentiment_query.order_by(func.count().desc())
    if top_sentiment:
        by_sentiment_query = by_sentiment_query.limit(top_sentiment)
    by_sentiment_rows = by_sentiment_query.all()

    by_symbol_query = base_query.with_entities(
        News.symbol.label("symbol"), func.count().label("count")
    ).group_by(News.symbol)
    by_symbol_query = by_symbol_query.order_by(func.count().desc())
    if top_symbol:
        by_symbol_query = by_symbol_query.limit(top_symbol)
    by_symbol_rows = by_symbol_query.all()

    by_date = [NewsCountByDateItem(date=row.date, count=row.count) for row in by_date_rows]
    by_sentiment = [NewsCountBySentimentItem(sentiment=row.sentiment, count=row.count) for row in by_sentiment_rows]
    by_symbol = [NewsCountBySymbolItem(symbol=row.symbol, count=row.count) for row in by_symbol_rows]
    set_json(
        cache_key,
        {
            "by_date": [item_to_dict(item) for item in by_date],
            "by_sentiment": [item_to_dict(item) for item in by_sentiment],
            "by_symbol": [item_to_dict(item) for item in by_symbol],
        },
        ttl=NEWS_STATS_CACHE_TTL,
    )
    return by_date, by_sentiment, by_symbol
