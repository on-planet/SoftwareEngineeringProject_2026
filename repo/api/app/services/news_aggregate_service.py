from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.news import News
from app.services.cache_utils import build_cache_key, item_to_dict
from app.schemas.news import NewsOut

NEWS_AGG_CACHE_TTL = 600


def _csv_field_filters(column, values: list[str]):
    conditions = []
    for value in values:
        text = str(value or "").strip()
        if not text:
            continue
        conditions.extend(
            [
                column == text,
                column.ilike(f"{text},%"),
                column.ilike(f"%,{text},%"),
                column.ilike(f"%,{text}"),
            ]
        )
    return or_(*conditions) if conditions else None


def list_news_aggregate(
    db: Session,
    symbols: list[str] | None = None,
    start: date | None = None,
    end: date | None = None,
    sentiments: list[str] | None = None,
    source_sites: list[str] | None = None,
    source_categories: list[str] | None = None,
    topic_categories: list[str] | None = None,
    time_buckets: list[str] | None = None,
    related_symbols: list[str] | None = None,
    related_sectors: list[str] | None = None,
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
        source_sites=source_sites,
        source_categories=source_categories,
        topic_categories=topic_categories,
        time_buckets=time_buckets,
        related_symbols=related_symbols,
        related_sectors=related_sectors,
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
    if source_sites:
        base_query = base_query.filter(News.source_site.in_(source_sites))
    if source_categories:
        base_query = base_query.filter(News.source_category.in_(source_categories))
    if topic_categories:
        base_query = base_query.filter(News.topic_category.in_(topic_categories))
    if time_buckets:
        base_query = base_query.filter(News.time_bucket.in_(time_buckets))
    if related_symbols:
        condition = _csv_field_filters(News.related_symbols, related_symbols)
        if condition is not None:
            base_query = base_query.filter(condition)
    if related_sectors:
        condition = _csv_field_filters(News.related_sectors, related_sectors)
        if condition is not None:
            base_query = base_query.filter(condition)
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
        "source_site": News.source_site,
        "source_category": News.source_category,
        "topic_category": News.topic_category,
        "time_bucket": News.time_bucket,
        "related_symbols": News.related_symbols,
        "related_sectors": News.related_sectors,
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
