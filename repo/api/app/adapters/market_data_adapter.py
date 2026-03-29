"""
市场数据适配器

提供统一的市场数据访问接口，隔离底层数据源实现。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Protocol


class MarketDataProvider(Protocol):
    """市场数据提供者协议"""

    def get_stock_basic(
        self,
        symbols: list[str] | None = None,
        *,
        force_refresh: bool = False,
        allow_stale_cache: bool = True,
    ) -> list[dict]:
        """获取股票基础信息"""
        ...

    def get_stock_quote(self, symbol: str) -> dict | None:
        """获取股票实时行情"""
        ...

    def get_stock_quote_detail(self, symbol: str) -> dict | None:
        """获取股票行情详情"""
        ...

    def get_stock_pankou(self, symbol: str) -> dict | None:
        """获取股票盘口数据"""
        ...

    def get_daily_history(
        self,
        symbol: str,
        *,
        count: int = 240,
        as_of: date | None = None,
    ) -> list[dict]:
        """获取日线历史数据"""
        ...

    def get_kline_history(
        self,
        symbol: str,
        *,
        period: str = "day",
        count: int = 240,
        as_of: date | None = None,
    ) -> list[dict]:
        """获取 K 线历史数据"""
        ...

    def get_recent_financials(
        self,
        symbol: str,
        *,
        count: int = 8,
    ) -> list[dict]:
        """获取最近的财务数据"""
        ...

    def get_stock_reports(
        self,
        symbol: str,
        *,
        count: int = 20,
    ) -> list[dict]:
        """获取研究报告"""
        ...

    def get_stock_earning_forecasts(
        self,
        symbol: str,
        *,
        count: int = 3,
    ) -> list[dict]:
        """获取盈利预测"""
        ...

    def load_stock_basics_cache(
        self,
        symbols: list[str] | None = None,
        *,
        allow_stale: bool = True,
    ) -> list[dict]:
        """从缓存加载股票基础信息"""
        ...

    def market_from_symbol(self, symbol: str) -> str:
        """从股票代码推断市场"""
        ...

    def normalize_index_symbol(self, symbol: str) -> str:
        """标准化指数代码"""
        ...


class MarketDataAdapter:
    """
    市场数据适配器
    
    作为 API 层和数据源之间的中间层，提供统一的数据访问接口。
    支持运行时切换不同的数据提供者实现。
    """

    def __init__(self, provider: MarketDataProvider):
        """
        初始化适配器
        
        Args:
            provider: 市场数据提供者实现
        """
        self._provider = provider

    def get_stock_basic(
        self,
        symbols: list[str] | None = None,
        *,
        force_refresh: bool = False,
        allow_stale_cache: bool = True,
    ) -> list[dict]:
        """获取股票基础信息"""
        return self._provider.get_stock_basic(
            symbols,
            force_refresh=force_refresh,
            allow_stale_cache=allow_stale_cache,
        )

    def get_stock_quote(self, symbol: str) -> dict | None:
        """获取股票实时行情"""
        return self._provider.get_stock_quote(symbol)

    def get_stock_quote_detail(self, symbol: str) -> dict | None:
        """获取股票行情详情"""
        return self._provider.get_stock_quote_detail(symbol)

    def get_stock_pankou(self, symbol: str) -> dict | None:
        """获取股票盘口数据"""
        return self._provider.get_stock_pankou(symbol)

    def get_daily_history(
        self,
        symbol: str,
        *,
        count: int = 240,
        as_of: date | None = None,
    ) -> list[dict]:
        """获取日线历史数据"""
        return self._provider.get_daily_history(symbol, count=count, as_of=as_of)

    def get_kline_history(
        self,
        symbol: str,
        *,
        period: str = "day",
        count: int = 240,
        as_of: date | None = None,
    ) -> list[dict]:
        """获取 K 线历史数据"""
        return self._provider.get_kline_history(
            symbol,
            period=period,
            count=count,
            as_of=as_of,
        )

    def get_recent_financials(
        self,
        symbol: str,
        *,
        count: int = 8,
    ) -> list[dict]:
        """获取最近的财务数据"""
        return self._provider.get_recent_financials(symbol, count=count)

    def get_stock_reports(
        self,
        symbol: str,
        *,
        count: int = 20,
    ) -> list[dict]:
        """获取研究报告"""
        return self._provider.get_stock_reports(symbol, count=count)

    def get_stock_earning_forecasts(
        self,
        symbol: str,
        *,
        count: int = 3,
    ) -> list[dict]:
        """获取盈利预测"""
        return self._provider.get_stock_earning_forecasts(symbol, count=count)

    def load_stock_basics_cache(
        self,
        symbols: list[str] | None = None,
        *,
        allow_stale: bool = True,
    ) -> list[dict]:
        """从缓存加载股票基础信息"""
        return self._provider.load_stock_basics_cache(symbols, allow_stale=allow_stale)

    def market_from_symbol(self, symbol: str) -> str:
        """从股票代码推断市场"""
        return self._provider.market_from_symbol(symbol)

    def normalize_index_symbol(self, symbol: str) -> str:
        """标准化指数代码"""
        return self._provider.normalize_index_symbol(symbol)
