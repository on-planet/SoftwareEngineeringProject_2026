from __future__ import annotations

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    limit: int
    offset: int


class CachedPage(Page[T], Generic[T]):
    cache_hit: bool | None = None
    as_of: str | None = None
    refresh_queued: bool | None = None
