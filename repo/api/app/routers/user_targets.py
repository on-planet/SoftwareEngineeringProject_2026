from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.auth_user import AuthUser
from app.routers.auth import get_current_user
from app.schemas.common import IdOut
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


@router.get("/user/me/bought-targets", response_model=list[BoughtTargetOut])
def list_my_bought_targets(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return list_bought_targets(db, int(current_user.id))


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
