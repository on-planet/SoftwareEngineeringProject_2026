"""
类型化缓存工具

提供类型安全的缓存操作，自动应用分级缓存策略。
"""
from __future__ import annotations

from datetime import datetime
from threading import Lock, Thread
from typing import Any, Callable, TypeVar

from app.core.cache import delete_cache, delete_cache_pattern, get_json, set_json
from app.core.cache_strategy import get_ttl_for_data_type

T = TypeVar("T")

_BACKGROUND_REFRESH_LOCK = Lock()
_BACKGROUND_REFRESH_KEYS: set[str] = set()


class TypedCache:
    """
    类型化缓存类
    
    自动应用数据类型对应的缓存策略。
    """

    def __init__(self, data_type: str):
        """
        初始化类型化缓存
        
        Args:
            data_type: 数据类型（如 "stock_quote", "financial_report"）
        """
        self.data_type = data_type
        self.default_ttl = get_ttl_for_data_type(data_type)

    def get(self, key: str) -> Any | None:
        """
        获取缓存数据
        
        Args:
            key: 缓存键
        
        Returns:
            缓存的数据，如果不存在返回 None
        """
        return get_json(key, data_type=self.data_type)

    def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """
        设置缓存数据
        
        Args:
            key: 缓存键
            value: 要缓存的数据
            ttl: 过期时间（秒），如果为 None 则使用默认 TTL
        
        Returns:
            bool: 是否成功
        """
        return set_json(key, value, ttl=ttl, data_type=self.data_type)

    def delete(self, key: str) -> bool:
        """
        删除缓存
        
        Args:
            key: 缓存键
        
        Returns:
            bool: 是否成功
        """
        return delete_cache(key)

    def delete_pattern(self, pattern: str) -> int:
        """
        批量删除匹配模式的缓存
        
        Args:
            pattern: 缓存键模式（支持通配符 *）
        
        Returns:
            int: 删除的数量
        """
        return delete_cache_pattern(pattern)

    def get_or_set(
        self,
        key: str,
        factory: Callable[[], T],
        ttl: int | None = None,
    ) -> T:
        """
        获取缓存，如果不存在则调用工厂函数生成并缓存
        
        Args:
            key: 缓存键
            factory: 数据生成函数
            ttl: 过期时间（秒），如果为 None 则使用默认 TTL
        
        Returns:
            缓存的数据或新生成的数据
        """
        cached = self.get(key)
        if cached is not None:
            return cached
        
        value = factory()
        self.set(key, value, ttl=ttl)
        return value


# 预定义的类型化缓存实例
stock_quote_cache = TypedCache("stock_quote")
stock_pankou_cache = TypedCache("stock_pankou")
stock_profile_cache = TypedCache("stock_profile")
daily_kline_cache = TypedCache("daily_kline")
intraday_kline_cache = TypedCache("intraday_kline")
financial_report_cache = TypedCache("financial_report")
stock_research_cache = TypedCache("stock_research")
macro_data_cache = TypedCache("macro_data")
news_list_cache = TypedCache("news_list")
user_portfolio_cache = TypedCache("user_portfolio")
stock_basic_cache = TypedCache("stock_basic")


def cache_with_type(data_type: str):
    """
    缓存装饰器，自动应用数据类型的缓存策略
    
    Args:
        data_type: 数据类型
    
    Returns:
        装饰器函数
    """
    def decorator(func: Callable) -> Callable:
        typed_cache = TypedCache(data_type)
        
        def wrapper(*args, **kwargs):
            # 生成缓存键（基于函数名和参数）
            cache_key = _generate_cache_key(func.__name__, args, kwargs)
            
            # 尝试从缓存获取
            cached = typed_cache.get(cache_key)
            if cached is not None:
                return cached
            
            # 调用原函数
            result = func(*args, **kwargs)
            
            # 缓存结果
            typed_cache.set(cache_key, result)
            
            return result
        
        return wrapper
    return decorator


def _generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """
    生成缓存键
    
    Args:
        func_name: 函数名
        args: 位置参数
        kwargs: 关键字参数
    
    Returns:
        str: 缓存键
    """
    import hashlib
    import json
    
    # 将参数序列化为字符串
    params_str = json.dumps(
        {"args": args, "kwargs": kwargs},
        sort_keys=True,
        default=str,
    )
    
    # 生成哈希
    params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
    
    return f"{func_name}:{params_hash}"


def _wrap_cached_value(value: Any) -> dict[str, Any]:
    return {
        "_cache": {
            "saved_at": datetime.now().isoformat(),
        },
        "value": value,
    }


def _unwrap_cached_value(payload: Any) -> tuple[Any | None, datetime | None]:
    if isinstance(payload, dict) and "_cache" in payload and "value" in payload:
        cache_meta = payload.get("_cache")
        saved_at: datetime | None = None
        if isinstance(cache_meta, dict):
            raw_saved_at = cache_meta.get("saved_at")
            if isinstance(raw_saved_at, str):
                try:
                    saved_at = datetime.fromisoformat(raw_saved_at)
                except ValueError:
                    saved_at = None
        return payload.get("value"), saved_at
    return payload, None


def _queue_background_refresh(cache_key: str, refresher: Callable[[], None]) -> bool:
    with _BACKGROUND_REFRESH_LOCK:
        if cache_key in _BACKGROUND_REFRESH_KEYS:
            return False
        _BACKGROUND_REFRESH_KEYS.add(cache_key)

    def _runner() -> None:
        try:
            refresher()
        finally:
            with _BACKGROUND_REFRESH_LOCK:
                _BACKGROUND_REFRESH_KEYS.discard(cache_key)

    Thread(target=_runner, name=f"typed-cache-refresh-{cache_key}", daemon=True).start()
    return True


def cached_call(
    data_type: str,
    key: str,
    loader: Callable[[], T],
    *,
    ttl: int | None = None,
    as_of: Callable[[T], str | None] | None = None,
    should_use_cached: Callable[[T], bool] | None = None,
    stale_after_seconds: int | None = None,
    background_refresher: Callable[[], None] | None = None,
    getter: Callable[..., Any] = get_json,
    setter: Callable[..., bool] = set_json,
) -> tuple[T, dict[str, Any]]:
    cached_payload = getter(key, data_type=data_type)
    cached_value, saved_at = _unwrap_cached_value(cached_payload)
    cache_is_usable = cached_value is not None and (should_use_cached(cached_value) if should_use_cached is not None else True)
    if cache_is_usable:
        refresh_queued = False
        if (
            background_refresher is not None
            and stale_after_seconds is not None
            and saved_at is not None
            and (datetime.now() - saved_at).total_seconds() >= stale_after_seconds
        ):
            refresh_queued = _queue_background_refresh(key, background_refresher)
        return cached_value, {
            "cache_hit": True,
            "as_of": as_of(cached_value) if as_of is not None else None,
            "refresh_queued": refresh_queued,
        }

    value = loader()
    setter(key, _wrap_cached_value(value), ttl=ttl, data_type=data_type)
    return value, {
        "cache_hit": False,
        "as_of": as_of(value) if as_of is not None else None,
        "refresh_queued": False,
    }
