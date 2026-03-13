from __future__ import annotations

from pydantic import BaseModel, Field


class PortfolioOut(BaseModel):
    user_id: int
    symbol: str
    avg_cost: float
    shares: float

    class Config:
        from_attributes = True


class PortfolioCreate(BaseModel):
    user_id: int
    symbol: str
    avg_cost: float = Field(..., ge=0)
    shares: float = Field(..., ge=0)


class PortfolioUpdate(BaseModel):
    avg_cost: float | None = Field(None, ge=0)
    shares: float | None = Field(None, ge=0)


class PortfolioBatchItem(BaseModel):
    symbol: str
    avg_cost: float = Field(..., ge=0)
    shares: float = Field(..., ge=0)


class PortfolioBatchIn(BaseModel):
    user_id: int
    items: list[PortfolioBatchItem]
