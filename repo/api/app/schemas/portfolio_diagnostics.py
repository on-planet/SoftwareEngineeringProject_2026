from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class PortfolioDiagnosticsExposureOut(BaseModel):
    label: str
    value: float
    weight: float


class PortfolioDiagnosticsHoldingOut(BaseModel):
    symbol: str
    name: str
    market: str
    sector: str
    weight: float
    current_value: float
    pnl_value: float
    pnl_pct: float


class PortfolioDiagnosticsStyleOut(BaseModel):
    code: str
    label: str
    score: float
    explanation: str


class PortfolioDiagnosticsSensitivityOut(BaseModel):
    code: str
    label: str
    scenario_name: str
    portfolio_change_pct: float
    direction: str
    explanation: str


class PortfolioDiagnosticsTagOut(BaseModel):
    code: str
    label: str
    tone: str
    explanation: str


class PortfolioDiagnosticsSummaryOut(BaseModel):
    as_of: date | None = None
    holdings_count: int
    total_cost: float
    total_value: float
    total_pnl: float
    total_pnl_pct: float
    sector_count: int
    top_sector: str | None = None
    top_market: str | None = None
    top3_weight: float


class PortfolioDiagnosticsOut(BaseModel):
    schema_version: str = "portfolio-diagnostics.v1"
    summary: PortfolioDiagnosticsSummaryOut
    overview: str
    portrait: list[PortfolioDiagnosticsTagOut] = Field(default_factory=list)
    style_exposures: list[PortfolioDiagnosticsStyleOut] = Field(default_factory=list)
    macro_sensitivities: list[PortfolioDiagnosticsSensitivityOut] = Field(default_factory=list)
    sector_exposure: list[PortfolioDiagnosticsExposureOut] = Field(default_factory=list)
    market_exposure: list[PortfolioDiagnosticsExposureOut] = Field(default_factory=list)
    top_positions: list[PortfolioDiagnosticsHoldingOut] = Field(default_factory=list)
