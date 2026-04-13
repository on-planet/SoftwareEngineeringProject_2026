from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AdminUserOut(BaseModel):
    id: int
    email: str
    is_active: bool
    is_email_verified: bool
    is_admin: bool
    created_at: datetime | None = None
    last_login_at: datetime | None = None

    class Config:
        from_attributes = True


class AdminUserUpdateIn(BaseModel):
    is_active: bool | None = None
    is_admin: bool | None = None


class AdminSystemStatusOut(BaseModel):
    app_name: str
    database_url: str
    redis_url: str
    cache_stats: dict


class AdminClearCacheIn(BaseModel):
    pattern: str | None = None


class AdminClearCacheOut(BaseModel):
    cleared_count: int
    pattern: str | None = None


class AdminAccessLogEntry(BaseModel):
    method: str
    path: str
    client_ip: str
    status: int
    duration_ms: float
    timestamp: str


class AdminAccessStatsOut(BaseModel):
    total_requests: int
    unique_ips: int
    top_ips: list[dict]
    status_distribution: list[dict]
    path_distribution: list[dict]
    hourly_counts: list[dict]
