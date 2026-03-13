from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Any, Dict

try:
    import redis
except ImportError:  # pragma: no cover - optional dependency
    redis = None

from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)
DEFAULT_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DEFAULT_REDIS_TTL = int(os.getenv("REDIS_TTL", "3600"))


def _get_client():
    if redis is None:
        LOGGER.warning("redis 库未安装，跳过缓存写入")
        return None
    if not DEFAULT_REDIS_URL:
        LOGGER.warning("Redis URL 未配置，跳过缓存写入")
        return None
    try:
        return redis.from_url(DEFAULT_REDIS_URL)
    except Exception as exc:  # pragma: no cover - connection error
        LOGGER.warning("Redis 连接失败：%s", exc)
        return None


def _format_key_suffix(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


def _dump_payload(data: Dict[str, Any]) -> str:
    def _default(obj: Any):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return str(obj)

    return json.dumps(data, ensure_ascii=False, default=_default)


def _set_json(key: str, data: Dict[str, Any]) -> None:
    client = _get_client()
    if client is None:
        return
    if not data:
        LOGGER.info("Redis skip empty payload: %s", key)
        return
    try:
        client.set(key, _dump_payload(data), ex=DEFAULT_REDIS_TTL)
    except Exception as exc:  # pragma: no cover - redis failure
        LOGGER.warning("Redis 写入失败 [%s]：%s", key, exc)


def get_cache_string(key: str) -> str | None:
    client = _get_client()
    if client is None:
        return None
    try:
        value = client.get(key)
    except Exception as exc:  # pragma: no cover - redis failure
        LOGGER.warning("Redis 读取失败 [%s]：%s", key, exc)
        return None
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def cache_heatmap(as_of: date | str, data: Dict[str, Any]) -> None:
    """Cache heatmap data into Redis."""
    key = f"heatmap:{_format_key_suffix(as_of)}"
    _set_json(key, data)
    _set_json("heatmap:latest", data)


def cache_risk(symbol: str, data: Dict[str, Any]) -> None:
    """Cache risk metrics into Redis."""
    key = f"risk:{symbol}"
    _set_json(key, data)


def cache_risk_series(symbol: str, data: Dict[str, Any]) -> None:
    """Cache risk series into Redis."""
    key = f"risk_series:{symbol}"
    _set_json(key, data)


def cache_indicator(symbol: str, indicator: str, data: Dict[str, Any]) -> None:
    """Cache indicator series into Redis."""
    key = f"indicator:{symbol}:{indicator}"
    _set_json(key, data)


def cache_sector_exposure(as_of: date | str, data: Dict[str, Any]) -> None:
    """Cache sector exposure into Redis."""
    key = f"sector_exposure:{_format_key_suffix(as_of)}"
    _set_json(key, data)
    _set_json("sector_exposure:latest", data)


def cache_macro(as_of: date | str, data: Dict[str, Any]) -> None:
    """Cache macro metrics into Redis."""
    key = f"macro:{_format_key_suffix(as_of)}"
    _set_json(key, data)
    _set_json("macro:latest", data)
