"""
缓存管理模块

支持 Redis + 内存双层缓存，实现分级缓存策略。

优化说明：
- 支持不同数据类型使用不同的 TTL
- 实时数据优先使用内存缓存
- 长期数据优先使用 Redis 缓存
- 自动降级到内存缓存
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from threading import Lock
from typing import Any

try:
    import redis
except ImportError:  # pragma: no cover - optional dependency
    redis = None

from app.core.config import settings
from app.core.logger import get_logger
from app.core.cache_strategy import (
    get_ttl_for_data_type,
    should_use_memory_cache,
    DEFAULT_CACHE_TTL,
)

logger = get_logger("api.cache")
_redis_lock = Lock()
_memory_lock = Lock()
_redis_client = None
_redis_ready = False
_memory_cache: dict[str, tuple[datetime, object]] = {}

# 内存缓存统计
_memory_cache_stats = {
    "hits": 0,
    "misses": 0,
    "sets": 0,
    "evictions": 0,
}

# 内存缓存大小限制（条目数）
MAX_MEMORY_CACHE_SIZE = 10000


def get_redis_client():
    """获取 Redis 客户端（单例模式）"""
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
            # 测试连接
            _redis_client.ping()
            logger.info("Redis 连接成功")
        except Exception as exc:  # pragma: no cover - connection error
            logger.warning("Redis 连接失败，启用进程内缓存回退：%s", exc)
            _redis_client = None
        return _redis_client


def _memory_get(key: str) -> Any | None:
    """从内存缓存获取数据"""
    now = datetime.now()
    with _memory_lock:
        item = _memory_cache.get(key)
        if item is None:
            _memory_cache_stats["misses"] += 1
            return None
        expire_at, value = item
        if expire_at <= now:
            _memory_cache.pop(key, None)
            _memory_cache_stats["evictions"] += 1
            _memory_cache_stats["misses"] += 1
            return None
        _memory_cache_stats["hits"] += 1
        return value


def _memory_set(key: str, payload: Any, ttl: int | None = None) -> None:
    """设置内存缓存"""
    expire = datetime.now() + timedelta(seconds=ttl if ttl is not None else DEFAULT_CACHE_TTL)
    with _memory_lock:
        # 检查缓存大小限制
        if len(_memory_cache) >= MAX_MEMORY_CACHE_SIZE and key not in _memory_cache:
            # 清理过期条目
            _evict_expired_memory_cache()
            
            # 如果还是超过限制，清理最旧的条目
            if len(_memory_cache) >= MAX_MEMORY_CACHE_SIZE:
                _evict_oldest_memory_cache()
        
        _memory_cache[key] = (expire, payload)
        _memory_cache_stats["sets"] += 1


def _evict_expired_memory_cache() -> None:
    """清理过期的内存缓存条目（需要持有锁）"""
    now = datetime.now()
    expired_keys = [key for key, (expire_at, _) in _memory_cache.items() if expire_at <= now]
    for key in expired_keys:
        _memory_cache.pop(key, None)
        _memory_cache_stats["evictions"] += 1


def _evict_oldest_memory_cache(count: int = 100) -> None:
    """清理最旧的内存缓存条目（需要持有锁）"""
    if not _memory_cache:
        return
    
    # 按过期时间排序，清理最早过期的
    sorted_items = sorted(_memory_cache.items(), key=lambda x: x[1][0])
    for key, _ in sorted_items[:count]:
        _memory_cache.pop(key, None)
        _memory_cache_stats["evictions"] += 1


def get_json(key: str, data_type: str | None = None) -> Any | None:
    """
    从缓存获取 JSON 数据
    
    Args:
        key: 缓存键
        data_type: 数据类型（用于确定缓存策略）
    
    Returns:
        缓存的数据，如果不存在返回 None
    """
    # 优先使用内存缓存的数据类型
    if data_type and should_use_memory_cache(data_type):
        memory_value = _memory_get(key)
        if memory_value is not None:
            return memory_value
    
    client = get_redis_client()
    if client is None:
        return _memory_get(key)
    
    try:
        value = client.get(key)
        if value is None:
            return _memory_get(key)
        
        ttl = client.ttl(key)
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        
        payload = json.loads(value)
        
        # 同步到内存缓存
        memory_ttl = ttl if isinstance(ttl, int) and ttl > 0 else DEFAULT_CACHE_TTL
        _memory_set(key, payload, ttl=memory_ttl)
        
        return payload
    except Exception as exc:  # pragma: no cover - redis failure
        logger.warning("Redis 读取失败 [%s]：%s", key, exc)
        return _memory_get(key)


def set_json(
    key: str,
    payload: Any,
    ttl: int | None = None,
    data_type: str | None = None,
) -> bool:
    """
    设置 JSON 数据到缓存
    
    Args:
        key: 缓存键
        payload: 要缓存的数据
        ttl: 过期时间（秒），如果为 None 则根据 data_type 自动确定
        data_type: 数据类型（用于确定缓存策略）
    
    Returns:
        bool: 是否成功
    """
    # 根据数据类型确定 TTL
    if ttl is None and data_type:
        ttl = get_ttl_for_data_type(data_type)
    
    effective_ttl = ttl if ttl is not None else DEFAULT_CACHE_TTL
    
    # 写入内存缓存
    _memory_set(key, payload, ttl=effective_ttl)
    
    # 写入 Redis
    client = get_redis_client()
    if client is None:
        return True
    
    try:
        value = json.dumps(payload, ensure_ascii=False, default=str)
        client.set(key, value, ex=effective_ttl)
        return True
    except Exception as exc:  # pragma: no cover - redis failure
        logger.warning("Redis 写入失败 [%s]：%s", key, exc)
        return True


def delete_cache(key: str) -> bool:
    """
    删除缓存
    
    Args:
        key: 缓存键
    
    Returns:
        bool: 是否成功
    """
    # 从内存缓存删除
    with _memory_lock:
        _memory_cache.pop(key, None)
    
    # 从 Redis 删除
    client = get_redis_client()
    if client is None:
        return True
    
    try:
        client.delete(key)
        return True
    except Exception as exc:
        logger.warning("Redis 删除失败 [%s]：%s", key, exc)
        return False


def delete_cache_pattern(pattern: str) -> int:
    """
    批量删除匹配模式的缓存
    
    Args:
        pattern: 缓存键模式（支持通配符 *）
    
    Returns:
        int: 删除的数量
    """
    count = 0
    
    # 从内存缓存删除
    with _memory_lock:
        matching_keys = [key for key in _memory_cache.keys() if _match_pattern(key, pattern)]
        for key in matching_keys:
            _memory_cache.pop(key, None)
            count += 1
    
    # 从 Redis 删除
    client = get_redis_client()
    if client is None:
        return count
    
    try:
        keys = client.keys(pattern)
        if keys:
            client.delete(*keys)
            count += len(keys)
    except Exception as exc:
        logger.warning("Redis 批量删除失败 [%s]：%s", pattern, exc)
    
    return count


def _match_pattern(key: str, pattern: str) -> bool:
    """简单的模式匹配（支持 * 通配符）"""
    import re
    regex_pattern = pattern.replace("*", ".*")
    return bool(re.match(f"^{regex_pattern}$", key))


def get_cache_stats() -> dict:
    """
    获取缓存统计信息
    
    Returns:
        dict: 统计信息
    """
    with _memory_lock:
        memory_size = len(_memory_cache)
        memory_stats = dict(_memory_cache_stats)
    
    redis_info = {}
    client = get_redis_client()
    if client:
        try:
            info = client.info("stats")
            redis_info = {
                "keyspace_hits": info.get("keyspace_hits", 0),
                "keyspace_misses": info.get("keyspace_misses", 0),
                "total_commands_processed": info.get("total_commands_processed", 0),
            }
        except Exception:
            pass
    
    return {
        "memory_cache": {
            "size": memory_size,
            "max_size": MAX_MEMORY_CACHE_SIZE,
            **memory_stats,
        },
        "redis_cache": redis_info,
    }


def clear_memory_cache() -> int:
    """
    清空内存缓存
    
    Returns:
        int: 清理的条目数
    """
    with _memory_lock:
        count = len(_memory_cache)
        _memory_cache.clear()
        return count


# 向后兼容的默认 TTL
DEFAULT_CACHE_TTL = DEFAULT_CACHE_TTL
