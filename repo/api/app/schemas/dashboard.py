from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.event_stats import EventStatsOut
from app.schemas.futures import FuturesOut
from app.schemas.heatmap import HeatmapItemOut
from app.schemas.index import IndexOut
from app.schemas.macro import MacroOut
from app.schemas.news import NewsOut
from app.schemas.news_stats import NewsStatsOut
from app.schemas.pagination import CachedPage


class DashboardHeatmapOverviewOut(BaseModel):
    a: CachedPage[HeatmapItemOut]
    hk: CachedPage[HeatmapItemOut]


class DashboardOverviewQueryOut(BaseModel):
    as_of: date | None = None
    index_limit: int
    heatmap_limit: int
    macro_limit: int
    futures_limit: int
    news_limit: int


class DashboardStatsOverviewQueryOut(BaseModel):
    symbols: list[str] = Field(default_factory=list)
    event_types: list[str] = Field(default_factory=list)
    sentiments: list[str] = Field(default_factory=list)
    start: date | None = None
    end: date | None = None
    granularity: Literal["day", "week", "month"] = "day"
    top_date: int | None = None
    top_type: int | None = None
    top_sentiment: int | None = None
    top_symbol: int | None = None


class DashboardOverviewOut(BaseModel):
    schema_version: Literal["dashboard-overview.v1"] = "dashboard-overview.v1"
    query: DashboardOverviewQueryOut
    indices: CachedPage[IndexOut]
    heatmap: DashboardHeatmapOverviewOut
    macro_snapshot: CachedPage[MacroOut]
    futures: CachedPage[FuturesOut]
    top_news: CachedPage[NewsOut]
    cache_hit: bool | None = None
    as_of: str | None = None
    refresh_queued: bool | None = None


class DashboardStatsOverviewOut(BaseModel):
    schema_version: Literal["dashboard-stats-overview.v1"] = "dashboard-stats-overview.v1"
    query: DashboardStatsOverviewQueryOut
    events: EventStatsOut
    news: NewsStatsOut
    cache_hit: bool | None = None
    as_of: str | None = None
    refresh_queued: bool | None = None
