from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.cache import get_json
from app.models.macro import Macro
from app.schemas.macro import MacroCreate, MacroUpdate
from app.schemas.macro_series import MacroPoint
from app.utils.query_params import SortOrder


def list_macro(db: Session, start: date | None = None, end: date | None = None, sort: SortOrder = "desc"):
    """List macro indicators."""
    query = db.query(Macro)
    if start is not None:
        query = query.filter(Macro.date >= start)
    if end is not None:
        query = query.filter(Macro.date <= end)
    if sort == "asc":
        return query.order_by(Macro.date.asc()).all()
    return query.order_by(Macro.date.desc()).all()


def get_cached_macro(
    as_of: date | None = None,
    start: date | None = None,
    end: date | None = None,
    sort: SortOrder = "desc",
) -> list[dict] | None:
    """Get cached macro data from Redis (if any)."""
    if as_of is None and (start is not None or end is not None):
        return None
    key = "macro:latest" if as_of is None else f"macro:{as_of.isoformat()}"
    payload = get_json(key)
    if not isinstance(payload, dict):
        return None
    items = payload.get("items")
    if isinstance(items, list):
        normalized = []
        for item in items:
            if not isinstance(item, dict):
                continue
            key_value = item.get("key")
            date_value = item.get("date")
            value = item.get("value")
            score = item.get("score")
            if not key_value or not date_value or value is None:
                continue
            try:
                normalized.append(
                    {
                        "key": str(key_value),
                        "date": str(date_value),
                        "value": float(value),
                        "score": None if score is None else float(score),
                    }
                )
            except (TypeError, ValueError):
                continue
        if start is not None:
            normalized = [item for item in normalized if item.get("date") and item["date"] >= start.isoformat()]
        if end is not None:
            normalized = [item for item in normalized if item.get("date") and item["date"] <= end.isoformat()]
        normalized.sort(key=lambda item: item.get("date") or "", reverse=(sort == "desc"))
        return normalized or None
    return None


def get_macro_series(db: Session, key: str, start: date | None = None, end: date | None = None):
    """Get macro time series by key."""
    query = db.query(Macro).filter(Macro.key == key)
    if start is not None:
        query = query.filter(Macro.date >= start)
    if end is not None:
        query = query.filter(Macro.date <= end)
    rows = query.order_by(Macro.date.asc()).all()
    return [MacroPoint(date=row.date, value=float(row.value or 0), score=row.score) for row in rows]


def create_macro(db: Session, payload: MacroCreate):
    item = Macro(**payload.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_macro(db: Session, key: str, macro_date: date, payload: MacroUpdate):
    item = (
        db.query(Macro)
        .filter(Macro.key == key, Macro.date == macro_date)
        .first()
    )
    if item is None:
        return None
    data = payload.dict(exclude_unset=True)
    for field, value in data.items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def delete_macro(db: Session, key: str, macro_date: date) -> bool:
    item = (
        db.query(Macro)
        .filter(Macro.key == key, Macro.date == macro_date)
        .first()
    )
    if item is None:
        return False
    db.delete(item)
    db.commit()
    return True
