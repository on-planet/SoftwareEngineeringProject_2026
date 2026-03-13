from __future__ import annotations

import json

try:
    import redis
except ImportError:  # pragma: no cover - optional dependency
    redis = None

from app.core.config import settings
from app.core.logger import get_logger

DEFAULT_CACHE_TTL = 3600

logger = get_logger("api.cache")


def get_redis_client():
    if redis is None:
        logger.warning("redis 库未安装，跳过缓存")
        return None
    try:
        return redis.from_url(settings.redis_url)
    except Exception as exc:  # pragma: no cover - connection error
        logger.warning("Redis 连接失败：%s", exc)
        return None


def get_json(key: str):
    client = get_redis_client()
    if client is None:
        return None
    try:
        value = client.get(key)
        if value is None:
            return None
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        return json.loads(value)
    except Exception as exc:  # pragma: no cover - redis failure
        logger.warning("Redis 读取失败 [%s]：%s", key, exc)
        return None


def set_json(key: str, payload: dict, ttl: int | None = None) -> bool:
    client = get_redis_client()
    if client is None:
        return False
    try:
        value = json.dumps(payload, ensure_ascii=False, default=str)
        expire = ttl if ttl is not None else DEFAULT_CACHE_TTL
        client.set(key, value, ex=expire)
        return True
    except Exception as exc:  # pragma: no cover - redis failure
        logger.warning("Redis 写入失败 [%s]：%s", key, exc)
        return False
