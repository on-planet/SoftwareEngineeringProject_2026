from __future__ import annotations

from datetime import date

from app.core.cache import set_json

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
