from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class FxSpotQuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    currency_pair: str
    bid: float | None = None
    ask: float | None = None
    as_of: datetime | None = None
    source: str | None = None


class FxSwapQuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    currency_pair: str
    one_week: float | None = None
    one_month: float | None = None
    three_month: float | None = None
    six_month: float | None = None
    nine_month: float | None = None
    one_year: float | None = None
    as_of: datetime | None = None
    source: str | None = None


class FxPairQuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    currency_pair: str
    bid: float | None = None
    ask: float | None = None
    as_of: datetime | None = None
    source: str | None = None
