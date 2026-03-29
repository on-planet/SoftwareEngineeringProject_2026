from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.news_graph import NewsGraphOut
from app.services.news_graph_service import build_news_focus_graph, build_stock_news_graph

router = APIRouter(tags=["news_graph"])


@router.get("/news/graph/stock/{symbol}", response_model=NewsGraphOut)
def get_stock_news_graph(
    symbol: str,
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(18, ge=5, le=24),
    db: Session = Depends(get_db),
):
    return build_stock_news_graph(db, symbol, days=days, limit=limit)


@router.get("/news/graph/{news_id}", response_model=NewsGraphOut)
def get_news_focus_graph(
    news_id: int,
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(8, ge=3, le=12),
    db: Session = Depends(get_db),
):
    payload = build_news_focus_graph(db, news_id, days=days, limit=limit)
    if payload is None:
        raise HTTPException(status_code=404, detail="News not found")
    return payload
