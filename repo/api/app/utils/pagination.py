from __future__ import annotations

from fastapi import Query


def pagination_params(
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    return {"limit": limit, "offset": offset}
