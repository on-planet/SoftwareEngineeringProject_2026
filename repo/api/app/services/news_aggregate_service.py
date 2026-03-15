from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.news import News
from app.services.cache_utils import build_cache_key, item_to_dict
from app.schemas.news import NewsOut

NEWS_AGG_CACHE_TTL = 600


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
    cache_key = build_cache_key(
        "news:aggregate",
        symbols=symbols,
        start=start,
        end=end,
        sentiments=sentiments,
        keyword=keyword,
        sort_by=sort_by,
        limit=limit,
        offset=offset,
        sort=sort,
    )
    cached = get_json(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("items"), list) and isinstance(cached.get("total"), int):
        items = [NewsOut(**item) for item in cached.get("items") if isinstance(item, dict)]
        return items, cached.get("total")

    base_query = db.query(News)
    if symbols:
        base_query = base_query.filter(News.symbol.in_(symbols))
    if sentiments:
        base_query = base_query.filter(News.sentiment.in_(sentiments))
    if keyword:
        keyword_like = f"%{keyword}%"
        base_query = base_query.filter(
            or_(News.title.ilike(keyword_like), News.symbol.ilike(keyword_like))
        )
    if start is not None:
        base_query = base_query.filter(News.published_at >= start)
    if end is not None:
        base_query = base_query.filter(News.published_at <= end)

    deduped = (
        base_query.with_entities(func.max(News.id).label("id"))
        .group_by(
            News.symbol,
            News.title,
            News.sentiment,
            News.published_at,
            News.link,
            News.source,
        )
        .subquery()
    )
    query = db.query(News).join(deduped, News.id == deduped.c.id)
    total = db.query(func.count()).select_from(deduped).scalar() or 0
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
    set_json(
        cache_key,
        {"items": [item_to_dict(item) for item in items], "total": total},
        ttl=NEWS_AGG_CACHE_TTL,
    )
    return items, total
