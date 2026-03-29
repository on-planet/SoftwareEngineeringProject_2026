from __future__ import annotations

from threading import Lock
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)

_engine_lock = Lock()
_engine_cache: dict[str, Engine] = {}
_session_factory_cache: dict[str, sessionmaker] = {}


def get_engine(
    database_url: str,
    *,
    pool_size: int = 5,
    max_overflow: int = 5,
    pool_timeout: int = 30,
    pool_recycle: int = 1800,
    pool_pre_ping: bool = True,
    **kwargs: Any,
) -> Engine:
    """
    获取或创建数据库引擎（单例模式）。
    
    使用相同的 database_url 和配置参数会返回同一个引擎实例，
    避免重复创建连接池。
    
    Args:
        database_url: 数据库连接字符串
        pool_size: 连接池大小
        max_overflow: 最大溢出连接数
        pool_timeout: 连接超时时间（秒）
        pool_recycle: 连接回收时间（秒）
        pool_pre_ping: 是否在使用前 ping 连接
        **kwargs: 其他传递给 create_engine 的参数
    
    Returns:
        Engine: SQLAlchemy 引擎实例
    """
    # 创建缓存键（包含所有配置参数）
    cache_key = f"{database_url}|{pool_size}|{max_overflow}|{pool_timeout}|{pool_recycle}|{pool_pre_ping}"
    
    with _engine_lock:
        if cache_key in _engine_cache:
            return _engine_cache[cache_key]
        
        LOGGER.info(
            "创建新的数据库引擎: pool_size=%s, max_overflow=%s, pool_timeout=%s, pool_recycle=%s",
            pool_size,
            max_overflow,
            pool_timeout,
            pool_recycle,
        )
        
        engine = create_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=pool_pre_ping,
            **kwargs,
        )
        
        _engine_cache[cache_key] = engine
        return engine


def get_session_factory(
    database_url: str,
    *,
    pool_size: int = 5,
    max_overflow: int = 5,
    pool_timeout: int = 30,
    pool_recycle: int = 1800,
    autocommit: bool = False,
    autoflush: bool = False,
) -> sessionmaker:
    """
    获取或创建 Session 工厂（单例模式）。
    
    Args:
        database_url: 数据库连接字符串
        pool_size: 连接池大小
        max_overflow: 最大溢出连接数
        pool_timeout: 连接超时时间（秒）
        pool_recycle: 连接回收时间（秒）
        autocommit: 是否自动提交
        autoflush: 是否自动刷新
    
    Returns:
        sessionmaker: SQLAlchemy Session 工厂
    """
    cache_key = f"{database_url}|{autocommit}|{autoflush}"
    
    with _engine_lock:
        if cache_key in _session_factory_cache:
            return _session_factory_cache[cache_key]
        
        engine = get_engine(
            database_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
        )
        
        factory = sessionmaker(
            autocommit=autocommit,
            autoflush=autoflush,
            bind=engine,
        )
        
        _session_factory_cache[cache_key] = factory
        return factory


def create_session(
    database_url: str,
    *,
    pool_size: int = 5,
    max_overflow: int = 5,
    pool_timeout: int = 30,
    pool_recycle: int = 1800,
) -> Session:
    """
    创建新的数据库 Session。
    
    使用共享的连接池，避免重复创建引擎。
    
    Args:
        database_url: 数据库连接字符串
        pool_size: 连接池大小
        max_overflow: 最大溢出连接数
        pool_timeout: 连接超时时间（秒）
        pool_recycle: 连接回收时间（秒）
    
    Returns:
        Session: SQLAlchemy Session 实例
    """
    factory = get_session_factory(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
    )
    return factory()


def dispose_all_engines() -> None:
    """
    释放所有缓存的数据库引擎。
    
    通常在应用关闭时调用。
    """
    with _engine_lock:
        for cache_key, engine in _engine_cache.items():
            try:
                engine.dispose()
                LOGGER.info("已释放数据库引擎: %s", cache_key.split("|")[0])
            except Exception as exc:
                LOGGER.warning("释放引擎失败: %s", exc)
        _engine_cache.clear()
        _session_factory_cache.clear()
