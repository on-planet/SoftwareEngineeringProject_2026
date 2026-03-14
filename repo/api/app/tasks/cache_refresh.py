from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.cache import set_json
from app.models.macro import Macro

DEFAULT_HEATMAP_TTL = 3600
DEFAULT_RISK_TTL = 1800
DEFAULT_MACRO_TTL = 3600


def _format_as_of(as_of: date | str) -> str:
    if isinstance(as_of, date):
        return as_of.isoformat()
    return str(as_of)


def cache_heatmap(as_of: date | str, data: dict | list, ttl: int = DEFAULT_HEATMAP_TTL) -> None:
    if isinstance(data, list):
        payload = {"items": data}
    else:
        payload = {"items": data.get("items", [])}
    key = f"heatmap:{_format_as_of(as_of)}"
    set_json(key, payload, ttl=ttl)
    set_json("heatmap:latest", payload, ttl=ttl)


def cache_risk(symbol: str, data: dict, ttl: int = DEFAULT_RISK_TTL) -> None:
    key = f"risk:{symbol}"
    set_json(key, data, ttl=ttl)


def cache_macro(as_of: date | str, data: dict | list, ttl: int = DEFAULT_MACRO_TTL) -> None:
    if isinstance(data, list):
        payload = {"items": data}
    else:
        payload = {"items": data.get("items", [])}
    key = f"macro:{_format_as_of(as_of)}"
    set_json(key, payload, ttl=ttl)
    set_json("macro:latest", payload, ttl=ttl)


def rebuild_macro_cache(db: Session, as_of: date | None = None, ttl: int = DEFAULT_MACRO_TTL) -> int:
    """Rebuild macro snapshot cache from DB and overwrite stale Redis payloads."""
    query = db.query(Macro)
    if as_of is not None:
        query = query.filter(Macro.date <= as_of)
    rows = query.order_by(Macro.key.asc(), Macro.date.desc()).all()
    latest_by_key: dict[str, dict] = {}
    latest_date: date | None = as_of
    for row in rows:
        if row.key in latest_by_key:
            continue
        latest_by_key[row.key] = {
            "key": row.key,
            "date": row.date.isoformat(),
            "value": float(row.value or 0),
            "score": None if row.score is None else float(row.score),
        }
        if latest_date is None or row.date > latest_date:
            latest_date = row.date
    if not latest_by_key or latest_date is None:
        return 0
    items = list(latest_by_key.values())
    items.sort(key=lambda item: (item["date"], item["key"]), reverse=True)
    payload = {"items": items, "date": latest_date.isoformat()}
    set_json(f"macro:{latest_date.isoformat()}", payload, ttl=ttl)
    set_json("macro:latest", payload, ttl=ttl)
    return len(items)
