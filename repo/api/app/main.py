from contextlib import asynccontextmanager
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from etl.utils.env import load_project_env

load_project_env()

from fastapi import FastAPI, HTTPException
from starlette.middleware.gzip import GZipMiddleware

from app.core.db import SessionLocal
from app.core.handlers import http_error_handler, http_exception_handler
from app.core.middleware import RequestLogMiddleware
from app.routers import get_router_registrations
from app.services.auth_service import ensure_admin_user


@asynccontextmanager
async def lifespan(_: FastAPI):
    db = SessionLocal()
    try:
        ensure_admin_user(db)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="QuantPulse API", version="0.1.0", lifespan=lifespan)

    app.add_exception_handler(Exception, http_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    # GZip 压缩中间件（仅压缩 >1KB 的响应）
    # 对大型股票列表等大数据响应启用压缩，减少传输时间
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    app.add_middleware(RequestLogMiddleware)

    for registration in get_router_registrations():
        app.include_router(registration.router, prefix=registration.prefix)

    return app


app = create_app()
