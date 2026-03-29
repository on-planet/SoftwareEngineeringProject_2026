from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.index_insight import IndexInsightOut
from app.services.index_insight_service import get_index_insight

router = APIRouter(tags=["index"])


@router.get("/index/{symbol}/insights", response_model=IndexInsightOut)
def get_index_insight_route(
    symbol: str,
    as_of: date | None = Query(None),
    db: Session = Depends(get_db),
):
    return get_index_insight(db, symbol, as_of=as_of)

