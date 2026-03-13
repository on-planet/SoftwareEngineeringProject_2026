from __future__ import annotations

from pydantic import BaseModel


class PortfolioItemAnalysis(BaseModel):
    symbol: str
    shares: float
    avg_cost: float
    latest_price: float
    pnl: float
    pnl_pct: float
    sector: str | None = None


class PortfolioSummary(BaseModel):
    total_cost: float
    total_value: float
    total_pnl: float
    total_pnl_pct: float


class ExposureItem(BaseModel):
    sector: str
    value: float
    weight: float


class ConcentrationItem(BaseModel):
    symbol: str
    value: float
    weight: float


class PortfolioAnalysisOut(BaseModel):
    user_id: int
    items: list[PortfolioItemAnalysis]
    summary: PortfolioSummary
    sector_exposure: list[ExposureItem]
    top_holdings: list[ConcentrationItem]
