from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class StockPoolCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    market: str = Field("A", pattern="^(A|HK|US)$")
    symbols: list[str] = Field(default_factory=list)
    note: str = Field("", max_length=512)


class StockPoolUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    market: str | None = Field(default=None, pattern="^(A|HK|US)$")
    symbols: list[str] | None = None
    note: str | None = Field(default=None, max_length=512)


class StockPoolOut(BaseModel):
    id: int
    name: str
    market: str
    symbols: list[str] = Field(default_factory=list)
    note: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class StockFilterCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    market: str = Field("A", pattern="^(A|HK|US)$")
    keyword: str = Field("", max_length=128)
    sector: str = Field("", max_length=128)
    sort: str = Field("asc", pattern="^(asc|desc)$")


class StockFilterUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    market: str | None = Field(default=None, pattern="^(A|HK|US)$")
    keyword: str | None = Field(default=None, max_length=128)
    sector: str | None = Field(default=None, max_length=128)
    sort: str | None = Field(default=None, pattern="^(asc|desc)$")


class StockFilterOut(BaseModel):
    id: int
    name: str
    market: str
    keyword: str
    sector: str
    sort: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserWorkspaceOut(BaseModel):
    pools: list[StockPoolOut] = Field(default_factory=list)
    filters: list[StockFilterOut] = Field(default_factory=list)
