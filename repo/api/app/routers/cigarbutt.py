from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.services.cigarbutt_strategy_service import analyze_cigarbutt

router = APIRouter(tags=["strategy"])


@router.get("/strategy/cigarbutt/{symbol}")
def get_cigarbutt_analysis(symbol: str, db: Session = Depends(get_db)):
    """Run static-value cigar butt analysis for a single stock."""
    return analyze_cigarbutt(symbol, db)
