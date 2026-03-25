from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE
from app.schemas.pagination import Page
from app.schemas.stock_report_disclosure import StockReportDisclosureOut
from app.services.stock_report_service import list_stock_report_disclosures
from app.utils.query_params import pagination_params, sort_params

router = APIRouter(tags=["stock_report"])


@router.get(
    "/stock/report/disclosure",
    response_model=Page[StockReportDisclosureOut],
    responses={500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}}},
)
def list_stock_report_disclosures_route(
    market: str = Query("沪深京"),
    period: str | None = Query(None),
    symbol: str | None = Query(None),
    keyword: str | None = Query(None),
    refresh: bool = Query(False),
    paging: dict = Depends(pagination_params),
    sorting: dict = Depends(sort_params),
    db: Session = Depends(get_db),
):
    items, total, _ = list_stock_report_disclosures(
        db,
        market=market,
        period=period,
        symbol=symbol,
        keyword=keyword,
        limit=paging["limit"],
        offset=paging["offset"],
        sort=sorting["sort"],
        refresh=refresh,
    )
    return {"items": items, "total": total, **paging}
