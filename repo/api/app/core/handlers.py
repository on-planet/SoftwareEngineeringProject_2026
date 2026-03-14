from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.core.errors import ErrorCode
from app.core.logger import get_logger

logger = get_logger("api")


def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled error", extra={"path": request.url.path}, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"code": ErrorCode.INTERNAL_ERROR, "message": "Internal server error"},
    )


def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    logger.warning("HTTP error", extra={"path": request.url.path, "detail": exc.detail})
    code = ErrorCode.HTTP_ERROR
    if exc.status_code == 404:
        code = ErrorCode.NOT_FOUND
    elif exc.status_code == 400:
        code = ErrorCode.VALIDATION_ERROR
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": code, "message": str(exc.detail)},
    )
