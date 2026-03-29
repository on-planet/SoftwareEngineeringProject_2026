from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.news import NewsOut


class NewsGraphNodeOut(BaseModel):
    id: str
    type: str
    label: str
    size: float = 18
    sentiment: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NewsGraphEdgeOut(BaseModel):
    source: str
    target: str
    type: str
    weight: float = 1.0
    label: str | None = None


class NewsGraphExplanationOut(BaseModel):
    headline: str
    evidence: list[str] = Field(default_factory=list)
    risk_hint: str | None = None
    generated_by: str = "template"


class NewsGraphEntityOut(BaseModel):
    id: str
    type: str
    label: str
    sentiment: str | None = None


class NewsGraphChainStepOut(NewsGraphEntityOut):
    relation: str | None = None
    weight: float | None = None


class NewsGraphChainOut(BaseModel):
    id: str
    title: str
    summary: str | None = None
    strength: float = 1.0
    steps: list[NewsGraphChainStepOut] = Field(default_factory=list)


class NewsGraphEventOut(BaseModel):
    id: int
    symbol: str
    type: str
    title: str
    date: date
    link: str | None = None
    source: str | None = None


class NewsGraphImpactSummaryOut(BaseModel):
    related_news_count: int = 0
    related_event_count: int = 0
    propagation_chain_count: int = 0
    impact_chain_count: int = 0
    dominant_sentiment: str = "neutral"
    dominant_direction: str | None = None
    affected_symbols: list[NewsGraphEntityOut] = Field(default_factory=list)
    affected_sectors: list[NewsGraphEntityOut] = Field(default_factory=list)
    portfolio_hint: str | None = None


class NewsGraphOut(BaseModel):
    center_type: str
    center_id: str
    center_label: str
    days: int
    nodes: list[NewsGraphNodeOut] = Field(default_factory=list)
    edges: list[NewsGraphEdgeOut] = Field(default_factory=list)
    explanation: NewsGraphExplanationOut
    related_news: list[NewsOut] = Field(default_factory=list)
    related_events: list[NewsGraphEventOut] = Field(default_factory=list)
    propagation_chains: list[NewsGraphChainOut] = Field(default_factory=list)
    impact_chains: list[NewsGraphChainOut] = Field(default_factory=list)
    impact_summary: NewsGraphImpactSummaryOut
