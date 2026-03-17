from __future__ import annotations

from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.cache import get_json, set_json
from app.models.news import News
from app.services.cache_utils import build_cache_key, items_to_dicts
from app.schemas.news import NewsCreate, NewsUpdate
from app.utils.query_params import SortOrder

NEWS_CACHE_TTL = 600


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


def list_news(
    db: Session,
    symbol: str,
    limit: int = 20,
    offset: int = 0,
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
    sort: SortOrder = "desc",
):
    """List news by symbol."""
    cache_key = build_cache_key(
        "news:list",
        symbol=symbol,
        limit=limit,
        offset=offset,
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
        sort=sort,
    )
    cached = get_json(cache_key)
    if isinstance(cached, dict) and isinstance(cached.get("items"), list) and isinstance(cached.get("total"), int):
        return cached["items"], cached["total"]

    query = db.query(News).filter(News.symbol == symbol)
    if sentiments:
        query = query.filter(News.sentiment.in_(sentiments))
    if source_sites:
        query = query.filter(News.source_site.in_(source_sites))
    if source_categories:
        query = query.filter(News.source_category.in_(source_categories))
    if topic_categories:
        query = query.filter(News.topic_category.in_(topic_categories))
    if time_buckets:
        query = query.filter(News.time_bucket.in_(time_buckets))
    if related_symbols:
        condition = _csv_field_filters(News.related_symbols, related_symbols)
        if condition is not None:
            query = query.filter(condition)
    if related_sectors:
        condition = _csv_field_filters(News.related_sectors, related_sectors)
        if condition is not None:
            query = query.filter(condition)
    if keyword:
        keyword_like = f"%{keyword}%"
        query = query.filter(News.title.ilike(keyword_like))
    if start is not None:
        query = query.filter(News.published_at >= start)
    if end is not None:
        query = query.filter(News.published_at <= end)
    total = query.count()
    sort_fields = {
        "published_at": News.published_at,
        "title": News.title,
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
    items = (
        query.order_by(*ordering)
        .offset(offset)
        .limit(limit)
        .all()
    )
    set_json(cache_key, {"items": items_to_dicts(items), "total": total}, ttl=NEWS_CACHE_TTL)
    return items, total


def create_news(db: Session, payload: NewsCreate):
    item = News(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_news(db: Session, news_id: int, payload: NewsUpdate):
    item = db.query(News).filter(News.id == news_id).first()
    if item is None:
        return None
    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete_news(db: Session, news_id: int) -> bool:
    item = db.query(News).filter(News.id == news_id).first()
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
