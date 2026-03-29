from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Date, func
from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.core.typed_cache import cached_call
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
    return_meta: bool = False,
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

    def _infer_as_of(payload: dict[str, Any]) -> str | None:
        rows = payload.get("by_date")
        if not isinstance(rows, list) or not rows:
            return None
        dates = [str(item.get("date")) for item in rows if isinstance(item, dict) and item.get("date")]
        return max(dates) if dates else None

    def _build_payload() -> dict[str, list[dict[str, Any]]]:
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
        return {
            "by_date": [item_to_dict(item) for item in by_date],
            "by_sentiment": [item_to_dict(item) for item in by_sentiment],
            "by_symbol": [item_to_dict(item) for item in by_symbol],
        }

    payload, cache_meta = cached_call(
        "news_stats",
        cache_key,
        _build_payload,
        ttl=NEWS_STATS_CACHE_TTL,
        as_of=_infer_as_of,
        getter=get_json,
        setter=set_json,
    )

    by_date = [NewsCountByDateItem(**row) for row in payload.get("by_date", []) if isinstance(row, dict)]
    by_sentiment = [
        NewsCountBySentimentItem(**row) for row in payload.get("by_sentiment", []) if isinstance(row, dict)
    ]
    by_symbol = [NewsCountBySymbolItem(**row) for row in payload.get("by_symbol", []) if isinstance(row, dict)]
    if return_meta:
        return by_date, by_sentiment, by_symbol, cache_meta
    return by_date, by_sentiment, by_symbol
