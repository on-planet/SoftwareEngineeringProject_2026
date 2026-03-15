from __future__ import annotations

import json
from datetime import datetime, timedelta
from threading import Lock

try:
    import redis
except ImportError:  # pragma: no cover - optional dependency
    redis = None

from app.core.config import settings
from app.core.logger import get_logger

DEFAULT_CACHE_TTL = 3600

logger = get_logger("api.cache")
_redis_lock = Lock()
_memory_lock = Lock()
_redis_client = None
_redis_ready = False
_memory_cache: dict[str, tuple[datetime, object]] = {}


def get_redis_client():
    global _redis_client, _redis_ready
    with _redis_lock:
        if _redis_ready:
            return _redis_client
        _redis_ready = True
        if redis is None:
            logger.warning("redis 库未安装，启用进程内缓存回退")
            return None
        try:
            _redis_client = redis.from_url(settings.redis_url)
        except Exception as exc:  # pragma: no cover - connection error
            logger.warning("Redis 连接失败，启用进程内缓存回退：%s", exc)
            _redis_client = None
        return _redis_client


def _memory_get(key: str):
    now = datetime.now()
    with _memory_lock:
        item = _memory_cache.get(key)
        if item is None:
            return None
        expire_at, value = item
        if expire_at <= now:
            _memory_cache.pop(key, None)
            return None
        return value


def _memory_set(key: str, payload, ttl: int | None = None) -> None:
    expire = datetime.now() + timedelta(seconds=ttl if ttl is not None else DEFAULT_CACHE_TTL)
    with _memory_lock:
        _memory_cache[key] = (expire, payload)


def get_json(key: str):
    client = get_redis_client()
    if client is None:
        return _memory_get(key)
    try:
        value = client.get(key)
        if value is None:
            return _memory_get(key)
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        payload = json.loads(value)
        _memory_set(key, payload)
        return payload
    except Exception as exc:  # pragma: no cover - redis failure
        logger.warning("Redis 读取失败 [%s]：%s", key, exc)
        return _memory_get(key)


def set_json(key: str, payload, ttl: int | None = None) -> bool:
    _memory_set(key, payload, ttl=ttl)
    client = get_redis_client()
    if client is None:
        return True
    try:
        value = json.dumps(payload, ensure_ascii=False, default=str)
        expire = ttl if ttl is not None else DEFAULT_CACHE_TTL
        client.set(key, value, ex=expire)
        return True
    except Exception as exc:  # pragma: no cover - redis failure
        logger.warning("Redis 写入失败 [%s]：%s", key, exc)
        return True
