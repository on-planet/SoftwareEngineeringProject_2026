from __future__ import annotations

from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.news import News
from app.schemas.news import NewsOut


def list_news_aggregate(
    db: Session,
    symbols: list[str] | None = None,
    start: date | None = None,
    end: date | None = None,
    sentiments: list[str] | None = None,
    keyword: str | None = None,
    sort_by: list[str] | None = None,
    limit: int = 100,
    offset: int = 0,
    sort: str = "desc",
):
    query = db.query(News)
    if symbols:
        query = query.filter(News.symbol.in_(symbols))
    if sentiments:
        query = query.filter(News.sentiment.in_(sentiments))
    if keyword:
        keyword_like = f"%{keyword}%"
        query = query.filter(
            or_(News.title.ilike(keyword_like), News.symbol.ilike(keyword_like))
        )
    if start is not None:
        query = query.filter(News.published_at >= start)
    if end is not None:
        query = query.filter(News.published_at <= end)
    total = query.count()
    sort_fields = {
        "published_at": News.published_at,
        "title": News.title,
        "symbol": News.symbol,
        "sentiment": News.sentiment,
    }
    sort_keys = [key for key in (sort_by or ["published_at"]) if key in sort_fields]
    if not sort_keys:
        sort_keys = ["published_at"]
    ordering = [
        (sort_fields[key].asc() if sort == "asc" else sort_fields[key].desc())
        for key in sort_keys
    ]
    rows = (
        query.order_by(*ordering)
        .offset(offset)
        .limit(limit)
        .all()
    )
    items = [NewsOut.from_orm(row) for row in rows]
    return items, total
