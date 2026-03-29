from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.auth_user import AuthUser
from app.routers.auth import get_current_user
from app.schemas.common import IdOut
from app.schemas.portfolio_diagnostics import PortfolioDiagnosticsOut
from app.schemas.portfolio_stress import (
    PortfolioScenarioLabIn,
    PortfolioScenarioLabOut,
    PortfolioStressOut,
    PortfolioStressPreviewIn,
    PortfolioStressScenarioOut,
)
from app.schemas.user_targets import (
    BoughtTargetBatchUpsertIn,
    BoughtTargetOut,
    BoughtTargetUpsertIn,
    WatchTargetBatchUpsertIn,
    WatchTargetCreateIn,
    WatchTargetOut,
)
from app.services.user_targets_service import (
    batch_upsert_bought_targets,
    batch_upsert_watch_targets,
    delete_bought_target,
    delete_watch_target,
    list_bought_targets,
    list_watch_targets,
    upsert_bought_target,
    upsert_watch_target,
)
from app.services.portfolio_diagnostics_service import get_bought_target_diagnostics, get_watch_target_diagnostics
from app.services.portfolio_scenario_lab_service import run_portfolio_scenario_lab
from app.services.portfolio_stress_service import (
    get_bought_target_stress_test,
    get_watch_target_stress_test,
    preview_custom_bought_target_stress_test,
    preview_custom_watch_target_stress_test,
)

router = APIRouter(tags=["user_targets"])


@router.get("/user/me/watch-targets", response_model=list[WatchTargetOut])
def list_my_watch_targets(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return list_watch_targets(db, int(current_user.id))


@router.post("/user/me/watch-targets", response_model=WatchTargetOut)
def upsert_my_watch_target(
    payload: WatchTargetCreateIn,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    item = upsert_watch_target(db, int(current_user.id), payload.symbol)
    if item is None:
        raise HTTPException(status_code=400, detail="Invalid symbol")
    return item


@router.post("/user/me/watch-targets/batch", response_model=list[WatchTargetOut])
def upsert_my_watch_targets_batch(
    payload: WatchTargetBatchUpsertIn,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return batch_upsert_watch_targets(db, int(current_user.id), payload.symbols)


@router.delete("/user/me/watch-targets/{symbol}", response_model=IdOut)
def delete_my_watch_target(
    symbol: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    ok = delete_watch_target(db, int(current_user.id), symbol)
    if not ok:
        raise HTTPException(status_code=404, detail="Watch target not found")
    return {"id": int(current_user.id)}


@router.get("/user/me/watch-targets/stress-test", response_model=PortfolioStressOut)
def get_my_watch_target_stress_test(
    position_limit: int = 8,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return get_watch_target_stress_test(
        db,
        int(current_user.id),
        position_limit=max(1, min(20, int(position_limit))),
    )


@router.post("/user/me/watch-targets/stress-test/custom", response_model=PortfolioStressScenarioOut)
def preview_my_watch_target_stress_test(
    payload: PortfolioStressPreviewIn,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return preview_custom_watch_target_stress_test(db, int(current_user.id), payload)


@router.post("/user/me/watch-targets/stress-test/lab", response_model=PortfolioScenarioLabOut)
def run_my_watch_target_scenario_lab(
    payload: PortfolioScenarioLabIn,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        return run_portfolio_scenario_lab(db, int(current_user.id), payload, target_type="watch")
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/user/me/watch-targets/diagnostics", response_model=PortfolioDiagnosticsOut)
def get_my_watch_target_diagnostics(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return get_watch_target_diagnostics(db, int(current_user.id))


@router.get("/user/me/bought-targets", response_model=list[BoughtTargetOut])
def list_my_bought_targets(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return list_bought_targets(db, int(current_user.id))


@router.get("/user/me/bought-targets/stress-test", response_model=PortfolioStressOut)
def get_my_bought_target_stress_test(
    position_limit: int = 8,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return get_bought_target_stress_test(
        db,
        int(current_user.id),
        position_limit=max(1, min(20, int(position_limit))),
    )


@router.post("/user/me/bought-targets/stress-test/custom", response_model=PortfolioStressScenarioOut)
def preview_my_bought_target_stress_test(
    payload: PortfolioStressPreviewIn,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return preview_custom_bought_target_stress_test(db, int(current_user.id), payload)


@router.post("/user/me/bought-targets/stress-test/lab", response_model=PortfolioScenarioLabOut)
def run_my_bought_target_scenario_lab(
    payload: PortfolioScenarioLabIn,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    try:
        return run_portfolio_scenario_lab(db, int(current_user.id), payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/user/me/bought-targets/diagnostics", response_model=PortfolioDiagnosticsOut)
def get_my_bought_target_diagnostics(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return get_bought_target_diagnostics(db, int(current_user.id))


@router.post("/user/me/bought-targets", response_model=BoughtTargetOut)
def upsert_my_bought_target(
    payload: BoughtTargetUpsertIn,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    item = upsert_bought_target(db, int(current_user.id), payload)
    if item is None:
        raise HTTPException(status_code=400, detail="Invalid bought target payload")
    return item


@router.post("/user/me/bought-targets/batch", response_model=list[BoughtTargetOut])
def upsert_my_bought_targets_batch(
    payload: BoughtTargetBatchUpsertIn,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return batch_upsert_bought_targets(db, int(current_user.id), payload.items)


@router.delete("/user/me/bought-targets/{symbol}", response_model=IdOut)
def delete_my_bought_target(
    symbol: str,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    ok = delete_bought_target(db, int(current_user.id), symbol)
    if not ok:
        raise HTTPException(status_code=404, detail="Bought target not found")
    return {"id": int(current_user.id)}
