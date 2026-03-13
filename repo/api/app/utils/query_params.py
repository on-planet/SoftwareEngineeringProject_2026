from __future__ import annotations

from typing import Literal

from fastapi import Query

SortOrder = Literal["asc", "desc"]


def pagination_params(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return {"limit": limit, "offset": offset}


def sort_params(
    sort: SortOrder = Query("desc"),
):
    return {"sort": sort}
