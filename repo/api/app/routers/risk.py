from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.error import ErrorResponse
from app.schemas.examples import ERROR_EXAMPLE, RISK_EXAMPLE
from app.schemas.risk import RiskOut
from app.services.risk_service import get_risk_snapshot

router = APIRouter(tags=["risk"])


@router.get(
    "/risk/{symbol}",
    response_model=RiskOut,
    responses={
        200: {"content": {"application/json": {"example": RISK_EXAMPLE}}},
        404: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
        500: {"model": ErrorResponse, "content": {"application/json": {"example": ERROR_EXAMPLE}}},
    },
)
def get_risk(symbol: str, db: Session = Depends(get_db)):
    """获取风险指标缓存。"""
    payload = get_risk_snapshot(db, symbol) or get_risk_snapshot(db, "ALL")
    if not payload:
        return RiskOut(symbol=symbol, max_drawdown=None, volatility=None, as_of=None)
    return RiskOut(
        symbol=symbol,
        max_drawdown=payload.get("max_drawdown"),
        volatility=payload.get("volatility"),
        as_of=payload.get("as_of"),
        cache_hit=payload.get("cache_hit"),
    )
