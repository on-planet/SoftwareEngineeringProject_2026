from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

AlertRuleType = Literal["price", "event", "earnings"]
AlertPriceOperator = Literal["gte", "lte"]
AlertResearchKind = Literal["all", "report", "earning_forecast"]


class AlertRuleBaseIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    rule_type: AlertRuleType
    symbol: str = Field(..., min_length=1, max_length=32)
    price_operator: AlertPriceOperator | None = None
    threshold: float | None = Field(default=None, gt=0)
    event_type: str | None = Field(default=None, max_length=64)
    research_kind: AlertResearchKind | None = None
    lookback_days: int = Field(7, ge=1, le=30)
    is_active: bool = True
    note: str = Field("", max_length=512)

    @model_validator(mode="after")
    def validate_rule_fields(self):
        if self.rule_type == "price":
            if self.price_operator is None or self.threshold is None:
                raise ValueError("Price alert requires price_operator and threshold")
        elif self.rule_type == "event":
            if not self.event_type:
                raise ValueError("Event alert requires event_type")
        elif self.rule_type == "earnings":
            if self.research_kind is None:
                self.research_kind = "all"
        return self


class AlertRuleCreateIn(AlertRuleBaseIn):
    pass


class AlertRuleUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    price_operator: AlertPriceOperator | None = None
    threshold: float | None = Field(default=None, gt=0)
    event_type: str | None = Field(default=None, max_length=64)
    research_kind: AlertResearchKind | None = None
    lookback_days: int | None = Field(default=None, ge=1, le=30)
    is_active: bool | None = None
    note: str | None = Field(default=None, max_length=512)


class AlertRuleOut(BaseModel):
    id: int
    name: str
    rule_type: AlertRuleType
    symbol: str
    price_operator: AlertPriceOperator | None = None
    threshold: float | None = None
    event_type: str | None = None
    research_kind: AlertResearchKind | None = None
    lookback_days: int
    is_active: bool
    note: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class AlertRuleEvaluationOut(AlertRuleOut):
    triggered: bool
    status: str
    status_message: str
    explanation: str | None = None
    latest_value: float | None = None
    matched_at: str | None = None
    context_title: str | None = None


class AlertCenterOut(BaseModel):
    total: int
    triggered: int
    items: list[AlertRuleEvaluationOut] = Field(default_factory=list)
