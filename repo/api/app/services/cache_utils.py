from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any


def normalize_cache_part(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, (list, tuple, set)):
        items = [normalize_cache_part(item) for item in value if item is not None]
        if not items:
            return "none"
        return ",".join(sorted(items))
    return str(value)


def build_cache_key(prefix: str, **kwargs: Any) -> str:
    parts: list[str] = [prefix]
    for key in sorted(kwargs.keys()):
        parts.append(f"{key}={normalize_cache_part(kwargs[key])}")
    return "|".join(parts)


def _to_plain_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def item_to_dict(item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        return {key: _to_plain_value(value) for key, value in item.items()}
    if hasattr(item, "_mapping"):
        return {key: _to_plain_value(value) for key, value in dict(item._mapping).items()}
    if hasattr(item, "model_dump"):
        return item.model_dump()
    if hasattr(item, "dict"):
        return item.dict()
    if hasattr(item, "__table__"):
        columns = getattr(item.__table__, "columns", [])
        return {column.name: _to_plain_value(getattr(item, column.name)) for column in columns}
    return {}


def items_to_dicts(items: list[Any]) -> list[dict[str, Any]]:
    return [item_to_dict(item) for item in items]
