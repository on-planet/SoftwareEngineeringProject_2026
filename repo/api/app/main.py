from contextlib import asynccontextmanager

from etl.utils.env import load_project_env

load_project_env()

from fastapi import FastAPI, HTTPException

from app.core.handlers import http_error_handler, http_exception_handler
from app.core.middleware import RequestLogMiddleware
from app.routers import get_router_registrations


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="KiloQuant API", version="0.1.0", lifespan=lifespan)

    app.add_exception_handler(Exception, http_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)

    app.add_middleware(RequestLogMiddleware)

    for registration in get_router_registrations():
        app.include_router(registration.router, prefix=registration.prefix)

    return app


app = create_app()
