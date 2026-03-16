from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.common import IdOut
from app.schemas.news import NewsOut, NewsCreate, NewsUpdate
from app.schemas.pagination import Page
from app.schemas.error import ErrorResponse
from app.schemas.examples import NEWS_PAGE_EXAMPLE, ERROR_EXAMPLE
from app.services.news_service import (
    list_news as list_news_service,
    create_news,
    update_news,
    delete_news,
)
from app.utils.query_params import pagination_params, sort_params

router = APIRouter(tags=["news"])


@router.get(
    "/stock/{symbol}/news",
    response_model=Page[NewsOut],
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def list_news(
    symbol: str,
    start: date | None = Query(None),
    end: date | None = Query(None),
    sentiment: str | None = Query(None),
    sentiments: list[str] | None = Query(None),
    source_site: str | None = Query(None),
    source_sites: list[str] | None = Query(None),
    source_category: str | None = Query(None),
    source_categories: list[str] | None = Query(None),
    topic_category: str | None = Query(None),
    topic_categories: list[str] | None = Query(None),
    time_bucket: str | None = Query(None),
    time_buckets: list[str] | None = Query(None),
    keyword: str | None = Query(None),
    sort_by: list[str] | None = Query(None),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    """获取新闻列表。"""
    sentiments_filter = sentiments or ([sentiment] if sentiment else None)
    source_sites_filter = source_sites or ([source_site] if source_site else None)
    source_categories_filter = source_categories or ([source_category] if source_category else None)
    topic_categories_filter = topic_categories or ([topic_category] if topic_category else None)
    time_buckets_filter = time_buckets or ([time_bucket] if time_bucket else None)
    items, total = list_news_service(
        db,
        symbol,
        limit=paging["limit"],
        offset=paging["offset"],
        start=start,
        end=end,
        sentiments=sentiments_filter,
        source_sites=source_sites_filter,
        source_categories=source_categories_filter,
        topic_categories=topic_categories_filter,
        time_buckets=time_buckets_filter,
        keyword=keyword,
        sort_by=sort_by,
        sort=sorting["sort"],
    )
    return {"items": items, "total": total, **paging}


@router.post(
    "/news",
    response_model=NewsOut,
    responses={400: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def create_news_route(payload: NewsCreate, db: Session = Depends(get_db)):
    """创建新闻记录。"""
    return create_news(db, payload)


@router.patch(
    "/news/{news_id}",
    response_model=NewsOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def update_news_route(news_id: int, payload: NewsUpdate, db: Session = Depends(get_db)):
    """更新新闻记录。"""
    item = update_news(db, news_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="News not found")
    return item


@router.delete(
    "/news/{news_id}",
    response_model=IdOut,
    responses={404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
               500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def delete_news_route(news_id: int, db: Session = Depends(get_db)):
    """删除新闻记录。"""
    ok = delete_news(db, news_id)
    if not ok:
        raise HTTPException(status_code=404, detail="News not found")
    return {"id": news_id}
