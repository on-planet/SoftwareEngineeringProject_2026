"""
数据适配器工厂

提供全局的市场数据适配器实例。
"""
from __future__ import annotations

from threading import Lock

from app.adapters.market_data_adapter import MarketDataAdapter
from app.adapters.etl_market_provider import EtlMarketDataProvider

_adapter_lock = Lock()
_adapter_instance: MarketDataAdapter | None = None


def get_market_data_adapter() -> MarketDataAdapter:
    """
    获取市场数据适配器实例（单例模式）
    
    默认使用 ETL 提供者实现。未来可以通过配置切换到其他实现。
    
    Returns:
        MarketDataAdapter: 市场数据适配器实例
    """
    global _adapter_instance
    
    with _adapter_lock:
        if _adapter_instance is None:
            # 默认使用 ETL 提供者
            provider = EtlMarketDataProvider()
            _adapter_instance = MarketDataAdapter(provider)
        
        return _adapter_instance


def set_market_data_adapter(adapter: MarketDataAdapter) -> None:
    """
    设置自定义的市场数据适配器
    
    用于测试或切换到不同的数据源实现。
    
    Args:
        adapter: 自定义的适配器实例
    """
    global _adapter_instance
    
    with _adapter_lock:
        _adapter_instance = adapter
