from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, root_validator


class PortfolioStressPositionOut(BaseModel):
    symbol: str
    name: str
    market: str
    sector: str
    current_price: float
    current_value: float
    weight: float
    shock_pct: float
    projected_value: float
    value_change: float


class PortfolioStressBucketOut(BaseModel):
    label: str
    affected_value: float
    portfolio_weight: float
    value_change: float


class PortfolioStressScenarioOut(BaseModel):
    code: str
    name: str
    description: str
    rules: list[str] = Field(default_factory=list)
    projected_value: float
    portfolio_change: float
    portfolio_change_pct: float
    loss_amount: float
    loss_pct: float
    impacted_value: float
    impacted_weight: float
    average_shock_pct: float | None = None
    affected_positions: list[PortfolioStressPositionOut] = Field(default_factory=list)
    sector_impacts: list[PortfolioStressBucketOut] = Field(default_factory=list)
    market_impacts: list[PortfolioStressBucketOut] = Field(default_factory=list)


class PortfolioStressSummaryOut(BaseModel):
    as_of: date | None = None
    holdings_count: int
    total_value: float
    scenario_count: int
    worst_scenario_code: str | None = None
    worst_scenario_name: str | None = None
    worst_loss_amount: float
    worst_loss_pct: float
    max_impacted_weight: float


class PortfolioStressOut(BaseModel):
    summary: PortfolioStressSummaryOut
    scenarios: list[PortfolioStressScenarioOut] = Field(default_factory=list)


class PortfolioStressRuleIn(BaseModel):
    scope_type: str = Field(..., min_length=1, max_length=16)
    scope_value: str | None = Field(None, max_length=64)
    shock_pct: float = Field(..., ge=-0.95, le=0.95)

    @root_validator(skip_on_failure=True)
    def validate_scope(cls, values: dict):
        scope_type = str(values.get("scope_type") or "").strip().lower()
        scope_value = str(values.get("scope_value") or "").strip()
        allowed = {"all", "market", "sector", "symbol"}
        if scope_type not in allowed:
            raise ValueError("scope_type must be one of: all, market, sector, symbol")
        values["scope_type"] = scope_type
        values["scope_value"] = scope_value or None
        if scope_type != "all" and not values["scope_value"]:
            raise ValueError("scope_value is required when scope_type is not all")
        return values


class PortfolioStressPreviewIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    description: str = Field("", max_length=240)
    rules: list[PortfolioStressRuleIn] = Field(default_factory=list, min_items=1, max_items=12)
    position_limit: int = Field(8, ge=1, le=20)


class PortfolioScenarioLabIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=240)
    position_limit: int = Field(8, ge=1, le=20)


class PortfolioScenarioImpactOut(BaseModel):
    label: str
    direction: str
    rationale: str


class PortfolioScenarioLabClauseOut(BaseModel):
    text: str
    parser: str
    confidence: str
    headline: str
    explanation: str
    matched_template_code: str | None = None
    matched_template_name: str | None = None
    extracted_shock_pct: float | None = None
    extracted_bp: float | None = None
    rules: list[str] = Field(default_factory=list)


class PortfolioScenarioLabParseOut(BaseModel):
    input_text: str
    matched_template_code: str | None = None
    matched_template_name: str | None = None
    matched_template_codes: list[str] = Field(default_factory=list)
    matched_template_names: list[str] = Field(default_factory=list)
    confidence: str
    extracted_shock_pct: float | None = None
    headline: str
    explanation: str
    clauses: list[PortfolioScenarioLabClauseOut] = Field(default_factory=list)


class PortfolioScenarioLabOut(BaseModel):
    schema_version: str = "portfolio-scenario-lab.v1"
    parse: PortfolioScenarioLabParseOut
    scenario: PortfolioStressScenarioOut
    beneficiaries: list[PortfolioScenarioImpactOut] = Field(default_factory=list)
    losers: list[PortfolioScenarioImpactOut] = Field(default_factory=list)
