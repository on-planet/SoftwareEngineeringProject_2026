from __future__ import annotations

from time import perf_counter

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logger import get_logger

logger = get_logger("api.request")


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = perf_counter()
        response = await call_next(request)
        duration_ms = (perf_counter() - start) * 1000
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 2),
            },
        )
        return response
