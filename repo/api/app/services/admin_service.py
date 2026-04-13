from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.cache import clear_memory_cache, delete_cache_pattern, get_cache_stats
from app.core.config import settings
from app.core.middleware import get_access_logs, get_access_stats
from app.models.auth_user import AuthUser


def list_users(db: Session, *, limit: int = 20, offset: int = 0) -> tuple[list[AuthUser], int]:
    query = db.query(AuthUser).order_by(AuthUser.id.desc())
    total = query.count()
    users = query.offset(offset).limit(limit).all()
    return users, total


def update_user(db: Session, user_id: int, *, is_active: bool | None = None, is_admin: bool | None = None) -> AuthUser | None:
    user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
    if user is None:
        return None
    if is_active is not None:
        user.is_active = is_active
    if is_admin is not None:
        user.is_admin = is_admin
    db.commit()
    db.refresh(user)
    return user


def get_system_status() -> dict:
    return {
        "app_name": settings.app_name,
        "database_url": mask_sensitive_url(settings.database_url),
        "redis_url": mask_sensitive_url(settings.redis_url),
        "cache_stats": get_cache_stats(),
    }


def clear_cache(pattern: str | None = None) -> dict:
    if pattern:
        cleared_count = delete_cache_pattern(pattern)
        return {"cleared_count": cleared_count, "pattern": pattern}
    cleared_count = clear_memory_cache()
    client = _get_redis_client_or_none()
    if client:
        try:
            redis_keys = client.keys("*")
            if redis_keys:
                client.delete(*redis_keys)
                cleared_count += len(redis_keys)
        except Exception:
            pass
    return {"cleared_count": cleared_count, "pattern": None}


def mask_sensitive_url(url: str) -> str:
    import re
    return re.sub(r"://[^:]+:[^@]+@", "://***:***@", url)


def get_access_logs_service(limit: int = 200) -> list[dict]:
    return get_access_logs(limit=limit)


def get_access_stats_service() -> dict:
    return get_access_stats()


def _get_redis_client_or_none():
    from app.core.cache import get_redis_client
    try:
        return get_redis_client()
    except Exception:
        return None
