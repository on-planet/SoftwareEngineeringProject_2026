from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.auth_user import AuthUser
from app.routers.auth import get_current_user
from app.schemas.common import IdOut
from app.schemas.user_workspace import (
    StockFilterCreateIn,
    StockFilterOut,
    StockFilterUpdateIn,
    StockPoolCreateIn,
    StockPoolOut,
    StockPoolUpdateIn,
    UserWorkspaceOut,
)
from app.services.user_workspace_service import (
    create_saved_stock_filter,
    create_stock_pool,
    delete_saved_stock_filter,
    delete_stock_pool,
    list_saved_stock_filters,
    list_stock_pools,
    update_saved_stock_filter,
    update_stock_pool,
)

router = APIRouter(tags=["user_workspace"])


@router.get("/user/me/workspace", response_model=UserWorkspaceOut)
def get_my_workspace(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    user_id = int(current_user.id)
    return {
        "pools": list_stock_pools(db, user_id),
        "filters": list_saved_stock_filters(db, user_id),
    }


@router.get("/user/me/stock-pools", response_model=list[StockPoolOut])
def list_my_stock_pools(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return list_stock_pools(db, int(current_user.id))


@router.post("/user/me/stock-pools", response_model=StockPoolOut)
def create_my_stock_pool(
    payload: StockPoolCreateIn,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return create_stock_pool(db, int(current_user.id), payload)


@router.patch("/user/me/stock-pools/{pool_id}", response_model=StockPoolOut)
def update_my_stock_pool(
    pool_id: int,
    payload: StockPoolUpdateIn,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    item = update_stock_pool(db, int(current_user.id), pool_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Stock pool not found")
    return item


@router.delete("/user/me/stock-pools/{pool_id}", response_model=IdOut)
def delete_my_stock_pool(
    pool_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    ok = delete_stock_pool(db, int(current_user.id), pool_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Stock pool not found")
    return {"id": pool_id}


@router.get("/user/me/stock-filters", response_model=list[StockFilterOut])
def list_my_stock_filters(
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return list_saved_stock_filters(db, int(current_user.id))


@router.post("/user/me/stock-filters", response_model=StockFilterOut)
def create_my_stock_filter(
    payload: StockFilterCreateIn,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    return create_saved_stock_filter(db, int(current_user.id), payload)


@router.patch("/user/me/stock-filters/{filter_id}", response_model=StockFilterOut)
def update_my_stock_filter(
    filter_id: int,
    payload: StockFilterUpdateIn,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    item = update_saved_stock_filter(db, int(current_user.id), filter_id, payload)
    if item is None:
        raise HTTPException(status_code=404, detail="Saved filter not found")
    return item


@router.delete("/user/me/stock-filters/{filter_id}", response_model=IdOut)
def delete_my_stock_filter(
    filter_id: int,
    db: Session = Depends(get_db),
    current_user: AuthUser = Depends(get_current_user),
):
    ok = delete_saved_stock_filter(db, int(current_user.id), filter_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Saved filter not found")
    return {"id": filter_id}
