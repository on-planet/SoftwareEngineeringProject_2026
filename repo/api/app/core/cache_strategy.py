"""
缓存策略配置

定义不同数据类型的缓存 TTL 和策略。
"""
from __future__ import annotations

from enum import Enum
from typing import NamedTuple


class CacheLevel(str, Enum):
    """缓存级别"""
    REALTIME = "realtime"  # 实时数据（秒级）
    SHORT = "short"  # 短期数据（分钟级）
    MEDIUM = "medium"  # 中期数据（小时级）
    LONG = "long"  # 长期数据（天级）
    PERMANENT = "permanent"  # 永久数据（周级）


class CacheConfig(NamedTuple):
    """缓存配置"""
    ttl: int  # 过期时间（秒）
    level: CacheLevel  # 缓存级别
    description: str  # 描述


# 缓存策略配置
CACHE_STRATEGIES = {
    # 实时行情数据（5秒）
    CacheLevel.REALTIME: CacheConfig(
        ttl=5,
        level=CacheLevel.REALTIME,
        description="实时行情、盘口数据"
    ),
    
    # 短期数据（5分钟）
    CacheLevel.SHORT: CacheConfig(
        ttl=300,
        level=CacheLevel.SHORT,
        description="分钟级K线、实时指标"
    ),
    
    # 中期数据（1小时）
    CacheLevel.MEDIUM: CacheConfig(
        ttl=3600,
        level=CacheLevel.MEDIUM,
        description="日线数据、用户数据、新闻列表"
    ),
    
    # 长期数据（1天）
    CacheLevel.LONG: CacheConfig(
        ttl=86400,
        level=CacheLevel.LONG,
        description="财报数据、研究报告、宏观数据"
    ),
    
    # 永久数据（7天）
    CacheLevel.PERMANENT: CacheConfig(
        ttl=604800,
        level=CacheLevel.PERMANENT,
        description="股票基础信息、历史财报"
    ),
}


# 数据类型到缓存级别的映射
DATA_TYPE_CACHE_LEVELS = {
    # 实时数据（5秒）
    "stock_quote": CacheLevel.REALTIME,
    "stock_pankou": CacheLevel.REALTIME,
    "live_snapshot": CacheLevel.REALTIME,
    
    # 短期数据（5分钟）
    "intraday_kline": CacheLevel.SHORT,
    "realtime_indicator": CacheLevel.SHORT,
    "risk_snapshot": CacheLevel.SHORT,
    
    # 中期数据（1小时）
    "daily_kline": CacheLevel.MEDIUM,
    "stock_profile": CacheLevel.MEDIUM,
    "user_portfolio": CacheLevel.MEDIUM,
    "user_workspace": CacheLevel.MEDIUM,
    "news_list": CacheLevel.MEDIUM,
    "news_stats": CacheLevel.MEDIUM,
    "event_stats": CacheLevel.MEDIUM,
    "dashboard_overview": CacheLevel.MEDIUM,
    "dashboard_stats": CacheLevel.MEDIUM,
    "sector_exposure": CacheLevel.MEDIUM,
    "heatmap": CacheLevel.MEDIUM,
    
    # 长期数据（1天）
    "financial_report": CacheLevel.LONG,
    "stock_research": CacheLevel.LONG,
    "earning_forecast": CacheLevel.LONG,
    "macro_data": CacheLevel.LONG,
    "fund_holdings": CacheLevel.LONG,
    "insider_trade": CacheLevel.LONG,
    "buyback": CacheLevel.LONG,
    
    # 永久数据（7天）
    "stock_basic": CacheLevel.PERMANENT,
    "index_constituent": CacheLevel.PERMANENT,
    "historical_financial": CacheLevel.PERMANENT,
}


def get_ttl_for_data_type(data_type: str) -> int:
    """
    根据数据类型获取 TTL
    
    Args:
        data_type: 数据类型（如 "stock_quote", "financial_report"）
    
    Returns:
        int: TTL（秒）
    """
    level = DATA_TYPE_CACHE_LEVELS.get(data_type, CacheLevel.MEDIUM)
    config = CACHE_STRATEGIES[level]
    return config.ttl


def get_ttl_for_cache_level(level: CacheLevel) -> int:
    """
    根据缓存级别获取 TTL
    
    Args:
        level: 缓存级别
    
    Returns:
        int: TTL（秒）
    """
    config = CACHE_STRATEGIES.get(level, CACHE_STRATEGIES[CacheLevel.MEDIUM])
    return config.ttl


def get_cache_key_prefix(data_type: str) -> str:
    """
    根据数据类型获取缓存键前缀
    
    Args:
        data_type: 数据类型
    
    Returns:
        str: 缓存键前缀
    """
    # 可以根据数据类型返回不同的前缀
    # 便于批量清理和监控
    level = DATA_TYPE_CACHE_LEVELS.get(data_type, CacheLevel.MEDIUM)
    return f"{level.value}:"


def should_use_memory_cache(data_type: str) -> bool:
    """
    判断是否应该使用内存缓存
    
    实时数据和短期数据优先使用内存缓存，提高访问速度。
    
    Args:
        data_type: 数据类型
    
    Returns:
        bool: 是否使用内存缓存
    """
    level = DATA_TYPE_CACHE_LEVELS.get(data_type, CacheLevel.MEDIUM)
    return level in {CacheLevel.REALTIME, CacheLevel.SHORT}


def get_cache_config(data_type: str) -> CacheConfig:
    """
    获取数据类型的完整缓存配置
    
    Args:
        data_type: 数据类型
    
    Returns:
        CacheConfig: 缓存配置
    """
    level = DATA_TYPE_CACHE_LEVELS.get(data_type, CacheLevel.MEDIUM)
    return CACHE_STRATEGIES[level]


# 默认 TTL（向后兼容）
DEFAULT_CACHE_TTL = CACHE_STRATEGIES[CacheLevel.MEDIUM].ttl
