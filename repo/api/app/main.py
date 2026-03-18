from fastapi import FastAPI, HTTPException

from app.core.handlers import http_error_handler, http_exception_handler
from app.core.middleware import RequestLogMiddleware
from app.core.schema import init_schema
from etl.utils.env import load_project_env
from app.routers import (
    auth,
    index,
    stock,
    news,
    news_aggregate,
    news_stats,
    events,
    events_timeline,
    events_stats,
    heatmap,
    macro,
    user,
    risk,
    risk_series,
    buyback,
    insider,
    financials,
    indicators,
    kline,
    index_constituents,
    sector,
    fund_holdings,
    futures,
    user_targets,
)

app = FastAPI(title="KiloQuant API", version="0.1.0")

app.add_exception_handler(Exception, http_error_handler)
app.add_exception_handler(HTTPException, http_exception_handler)

app.add_middleware(RequestLogMiddleware)


@app.on_event("startup")
def startup() -> None:
    load_project_env()
    init_schema()

app.include_router(index.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(stock.router, prefix="/api")
app.include_router(news.router, prefix="/api")
app.include_router(news_aggregate.router, prefix="/api")
app.include_router(news_stats.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(events_timeline.router, prefix="/api")
app.include_router(events_stats.router, prefix="/api")
app.include_router(heatmap.router, prefix="/api")
app.include_router(macro.router, prefix="/api")
app.include_router(user.router, prefix="/api")
app.include_router(risk.router, prefix="/api")
app.include_router(risk_series.router, prefix="/api")
app.include_router(buyback.router, prefix="/api")
app.include_router(insider.router, prefix="/api")
app.include_router(financials.router, prefix="/api")
app.include_router(indicators.router, prefix="/api")
app.include_router(kline.router, prefix="/api")
app.include_router(index_constituents.router, prefix="/api")
app.include_router(sector.router, prefix="/api")
app.include_router(fund_holdings.router, prefix="/api")
app.include_router(futures.router, prefix="/api")
app.include_router(user_targets.router, prefix="/api")
