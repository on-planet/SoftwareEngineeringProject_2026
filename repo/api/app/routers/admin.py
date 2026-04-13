from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.routers.auth import require_admin
from app.schemas.admin import (
    AdminAccessLogEntry,
    AdminAccessStatsOut,
    AdminClearCacheIn,
    AdminClearCacheOut,
    AdminSystemStatusOut,
    AdminUserOut,
    AdminUserUpdateIn,
)
from app.schemas.pagination import Page
from app.services.admin_service import (
    clear_cache,
    get_access_logs_service,
    get_access_stats_service,
    get_system_status,
    list_users,
    update_user,
)

router = APIRouter(tags=["admin"])


@router.get("/admin/users", response_model=Page[AdminUserOut])
def get_users(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    users, total = list_users(db, limit=limit, offset=offset)
    return {"items": users, "total": total, "limit": limit, "offset": offset}


@router.patch("/admin/users/{user_id}", response_model=AdminUserOut)
def patch_user(
    user_id: int,
    payload: AdminUserUpdateIn,
    db: Session = Depends(get_db),
    current_user=Depends(require_admin),
):
    user = update_user(db, user_id, is_active=payload.is_active, is_admin=payload.is_admin)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.get("/admin/system", response_model=AdminSystemStatusOut)
def get_system(
    current_user=Depends(require_admin),
):
    return get_system_status()


@router.post("/admin/system/clear-cache", response_model=AdminClearCacheOut)
def post_clear_cache(
    payload: AdminClearCacheIn,
    current_user=Depends(require_admin),
):
    return clear_cache(payload.pattern)


@router.get("/admin/access/logs", response_model=list[AdminAccessLogEntry])
def get_access_logs_route(
    limit: int = 200,
    current_user=Depends(require_admin),
):
    return get_access_logs_service(limit=limit)


@router.get("/admin/access/stats", response_model=AdminAccessStatsOut)
def get_access_stats_route(
    current_user=Depends(require_admin),
):
    return get_access_stats_service()
