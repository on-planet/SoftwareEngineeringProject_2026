from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.schema import probe_database_connection

router = APIRouter(tags=["health"])
ROUTER_PREFIX = ""


@router.get("/health/live", include_in_schema=False)
def get_liveness():
    return {"status": "ok"}


@router.get("/health/ready", include_in_schema=False)
def get_readiness():
    ok, detail = probe_database_connection()
    payload = {
        "status": "ok" if ok else "degraded",
        "checks": {
            "database": "ok" if ok else "error",
        },
    }
    if detail:
        payload["detail"] = detail
    return JSONResponse(status_code=200 if ok else 503, content=payload)
