from __future__ import annotations

from collections import deque
from datetime import datetime
from threading import Lock
from time import perf_counter

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logger import get_logger

logger = get_logger("api.request")

_MAX_ACCESS_LOGS = 2000
_access_logs: deque[dict] = deque(maxlen=_MAX_ACCESS_LOGS)
_access_lock = Lock()


def record_access(method: str, path: str, client_ip: str, status: int, duration_ms: float) -> None:
    entry = {
        "method": method,
        "path": path,
        "client_ip": client_ip,
        "status": status,
        "duration_ms": round(duration_ms, 2),
        "timestamp": datetime.utcnow().isoformat(),
    }
    with _access_lock:
        _access_logs.append(entry)


def get_access_logs(limit: int = 200) -> list[dict]:
    with _access_lock:
        return list(_access_logs)[-limit:]


def get_access_stats() -> dict:
    from collections import Counter
    with _access_lock:
        logs = list(_access_logs)
    total = len(logs)
    if total == 0:
        return {
            "total_requests": 0,
            "unique_ips": 0,
            "top_ips": [],
            "status_distribution": [],
            "path_distribution": [],
            "hourly_counts": [],
        }
    ip_counter = Counter(log["client_ip"] for log in logs)
    status_counter = Counter(log["status"] for log in logs)
    path_counter = Counter(log["path"] for log in logs)
    hour_counter = Counter(log["timestamp"][:13] for log in logs)
    return {
        "total_requests": total,
        "unique_ips": len(ip_counter),
        "top_ips": [{"ip": ip, "count": cnt} for ip, cnt in ip_counter.most_common(10)],
        "status_distribution": [{"status": status, "count": cnt} for status, cnt in status_counter.most_common()],
        "path_distribution": [{"path": path, "count": cnt} for path, cnt in path_counter.most_common(10)],
        "hourly_counts": [{"hour": h, "count": cnt} for h, cnt in sorted(hour_counter.items())],
    }


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = perf_counter()
        response = await call_next(request)
        duration_ms = (perf_counter() - start) * 1000
        client_ip = request.client.host if request.client else ""
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip() or client_ip
        record_access(
            method=request.method,
            path=request.url.path,
            client_ip=client_ip or "unknown",
            status=response.status_code,
            duration_ms=duration_ms,
        )
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "client_ip": client_ip,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return response
