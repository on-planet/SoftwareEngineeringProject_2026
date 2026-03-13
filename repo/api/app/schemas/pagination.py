from __future__ import annotations

from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: List[T]
    total: int
    limit: int
    offset: int
