from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE
from app.schemas.news import NewsOut
from app.schemas.pagination import Page
from app.services.news_aggregate_service import list_news_aggregate
from app.utils.query_params import pagination_params, sort_params

router = APIRouter(tags=["news"])


@router.get(
    "/news/aggregate",
    response_model=Page[NewsOut],
    responses={
        200: {"content": {"application/json": {"example": {"items": [{"id": 1, "symbol": "000001.SH", "title": "示例新闻", "sentiment": "positive", "published_at": "2026-03-10T08:00:00Z"}], "total": 1, "limit": 20, "offset": 0}}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def get_news_aggregate(
    symbol: str | None = Query(None),
    symbols: list[str] | None = Query(None),
    sentiment: str | None = Query(None),
    sentiments: list[str] | None = Query(None),
    keyword: str | None = Query(None),
    sort_by: list[str] | None = Query(None),
    start: date | None = Query(None),
    end: date | None = Query(None),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    """聚合新闻列表（跨股票）。"""
    symbols_filter = symbols or ([symbol] if symbol else None)
    sentiments_filter = sentiments or ([sentiment] if sentiment else None)
    items, total = list_news_aggregate(
        db,
        symbols=symbols_filter,
        start=start,
        end=end,
        sentiments=sentiments_filter,
        keyword=keyword,
        sort_by=sort_by,
        limit=paging["limit"],
        offset=paging["offset"],
        sort=sorting["sort"],
    )
    return {"items": items, "total": total, **paging}
