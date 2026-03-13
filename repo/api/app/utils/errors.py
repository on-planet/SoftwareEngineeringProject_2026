from __future__ import annotations

from typing import Iterable

from fastapi import HTTPException


def ensure_found(entity, message: str = "Not found"):
    if entity is None:
        raise HTTPException(status_code=404, detail=message)
    return entity


def ensure_non_empty(items: Iterable, message: str = "No data"):
    if not items:
        raise HTTPException(status_code=404, detail=message)
    return items
