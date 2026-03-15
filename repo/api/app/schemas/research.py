from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ResearchItemOut(BaseModel):
    title: str
    published_at: datetime | None = None
    link: str | None = None
    summary: str | None = None
    institution: str | None = None
    rating: str | None = None
    source: str | None = None


class ResearchPanelOut(BaseModel):
    symbol: str
    reports: list[ResearchItemOut]
    earning_forecasts: list[ResearchItemOut]
