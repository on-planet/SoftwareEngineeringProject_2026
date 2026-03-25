from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BondMarketQuoteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    quote_org: str | None = None
    bond_name: str
    buy_net_price: float | None = None
    sell_net_price: float | None = None
    buy_yield: float | None = None
    sell_yield: float | None = None
    as_of: datetime | None = None
    source: str | None = None


class BondMarketTradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    bond_name: str
    deal_net_price: float | None = None
    latest_yield: float | None = None
    change: float | None = None
    weighted_yield: float | None = None
    volume: float | None = None
    as_of: datetime | None = None
    source: str | None = None
