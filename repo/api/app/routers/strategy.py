from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.schemas.strategy import (
    SmokeButtBacktestOut,
    SmokeButtDetailOut,
    SmokeButtPageOut,
    SmokeButtTrainIn,
    SmokeButtTrainOut,
)
from app.services.smoke_butt_strategy_service import (
    AutoGluonUnavailableError,
    SmokeButtDataError,
    get_smoke_butt_backtest,
    get_smoke_butt_detail,
    list_smoke_butt_candidates,
    train_smoke_butt_strategy,
)
from app.utils.query_params import pagination_params

router = APIRouter(tags=["strategy"])


@router.get("/strategy/smoke-butt", response_model=SmokeButtPageOut)
def list_smoke_butt_strategy(
    market: str | None = Query(None, pattern="^(A|HK|US)$"),
    signal: str | None = Query(None, pattern="^(strong_buy|buy|watch|avoid)$"),
    paging: dict = Depends(pagination_params),
    db: Session = Depends(get_db),
):
    items, total, run = list_smoke_butt_candidates(
        db,
        market=market,
        signal=signal,
        limit=paging["limit"],
        offset=paging["offset"],
    )
    return {"items": items, "total": total, "limit": paging["limit"], "offset": paging["offset"], "run": run}


@router.get("/strategy/smoke-butt/backtest", response_model=SmokeButtBacktestOut | None)
def get_smoke_butt_backtest_route(
    market: str | None = Query(None, pattern="^(A|HK|US)$"),
    bucket_count: int = Query(5, ge=3, le=10),
    db: Session = Depends(get_db),
):
    try:
        return get_smoke_butt_backtest(db, market=market, bucket_count=bucket_count)
    except AutoGluonUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SmokeButtDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/strategy/smoke-butt/{symbol}", response_model=SmokeButtDetailOut | None)
def get_smoke_butt_strategy(symbol: str, db: Session = Depends(get_db)):
    return get_smoke_butt_detail(db, symbol)


@router.post("/strategy/smoke-butt/train", response_model=SmokeButtTrainOut)
def train_smoke_butt_strategy_route(payload: SmokeButtTrainIn, db: Session = Depends(get_db)):
    try:
        run, items = train_smoke_butt_strategy(
            db,
            as_of=payload.as_of,
            horizon_days=payload.horizon_days,
            sample_step=payload.sample_step,
            time_limit_seconds=payload.time_limit_seconds,
            force_retrain=payload.force_retrain,
        )
    except AutoGluonUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SmokeButtDataError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run": run, "items": items}
