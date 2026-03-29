"""
ETL 市场数据提供者

基于 ETL 层实现的市场数据提供者。
这是一个临时的适配器实现，用于保持向后兼容。
"""
from __future__ import annotations

from datetime import date

from etl.utils.env import load_project_env

load_project_env()

from etl.fetchers.market_client import get_stock_basic as _get_stock_basic
from etl.fetchers.snowball_client import (
    get_daily_history as _get_daily_history,
    get_kline_history as _get_kline_history,
    get_recent_financials as _get_recent_financials,
    get_stock_earning_forecasts as _get_stock_earning_forecasts,
    get_stock_pankou as _get_stock_pankou,
    get_stock_quote as _get_stock_quote,
    get_stock_quote_detail as _get_stock_quote_detail,
    get_stock_reports as _get_stock_reports,
    market_from_symbol as _market_from_symbol,
    normalize_index_symbol as _normalize_index_symbol,
)
from etl.utils.stock_basics_cache import load_stock_basics_cache as _load_stock_basics_cache


class EtlMarketDataProvider:
    """
    基于 ETL 层的市场数据提供者
    
    这是一个适配器实现，将 ETL 层的 fetchers 封装为统一接口。
    未来可以替换为其他实现（如直接调用第三方 API、使用消息队列等）。
    """

    def get_stock_basic(
        self,
        symbols: list[str] | None = None,
        *,
        force_refresh: bool = False,
        allow_stale_cache: bool = True,
    ) -> list[dict]:
        """获取股票基础信息"""
        return _get_stock_basic(
            symbols,
            force_refresh=force_refresh,
            allow_stale_cache=allow_stale_cache,
        )

    def get_stock_quote(self, symbol: str) -> dict | None:
        """获取股票实时行情"""
        return _get_stock_quote(symbol)

    def get_stock_quote_detail(self, symbol: str) -> dict | None:
        """获取股票行情详情"""
        return _get_stock_quote_detail(symbol)

    def get_stock_pankou(self, symbol: str) -> dict | None:
        """获取股票盘口数据"""
        return _get_stock_pankou(symbol)

    def get_daily_history(
        self,
        symbol: str,
        *,
        count: int = 240,
        as_of: date | None = None,
    ) -> list[dict]:
        """获取日线历史数据"""
        return _get_daily_history(symbol, count=count, as_of=as_of)

    def get_kline_history(
        self,
        symbol: str,
        *,
        period: str = "day",
        count: int = 240,
        as_of: date | None = None,
    ) -> list[dict]:
        """获取 K 线历史数据"""
        return _get_kline_history(symbol, period=period, count=count, as_of=as_of)

    def get_recent_financials(
        self,
        symbol: str,
        *,
        count: int = 8,
    ) -> list[dict]:
        """获取最近的财务数据"""
        return _get_recent_financials(symbol, count=count)

    def get_stock_reports(
        self,
        symbol: str,
        *,
        count: int = 20,
    ) -> list[dict]:
        """获取研究报告"""
        return _get_stock_reports(symbol, count=count)

    def get_stock_earning_forecasts(
        self,
        symbol: str,
        *,
        count: int = 3,
    ) -> list[dict]:
        """获取盈利预测"""
        return _get_stock_earning_forecasts(symbol, count=count)

    def load_stock_basics_cache(
        self,
        symbols: list[str] | None = None,
        *,
        allow_stale: bool = True,
    ) -> list[dict]:
        """从缓存加载股票基础信息"""
        return _load_stock_basics_cache(symbols, allow_stale=allow_stale)

    def market_from_symbol(self, symbol: str) -> str:
        """从股票代码推断市场"""
        return _market_from_symbol(symbol)

    def normalize_index_symbol(self, symbol: str) -> str:
        """标准化指数代码"""
        return _normalize_index_symbol(symbol)
