"""
ETL 市场数据提供者

基于 ETL Provider 层实现的统一市场数据入口。
所有业务代码应通过 DataProvider 获取数据，不再直接引用底层 fetchers。
"""
from __future__ import annotations

from datetime import date

from etl.providers import get_provider

_provider = get_provider()


class EtlMarketDataProvider:
    """
    基于 ETL Provider 层的市场数据适配器。
    保持向后兼容的接口，内部已迁移到统一的 DataProvider 门面。
    """

    def get_stock_basic(
        self,
        symbols: list[str] | None = None,
        *,
        force_refresh: bool = False,
        allow_stale_cache: bool = True,
    ) -> list[dict]:
        """获取股票基础信息"""
        return _provider.market.get_stock_basic(
            symbols,
            force_refresh=force_refresh,
            allow_stale_cache=allow_stale_cache,
        )

    def get_stock_quote(self, symbol: str) -> dict | None:
        """获取股票实时行情"""
        return _provider.market.get_stock_quote(symbol)

    def get_stock_quote_detail(self, symbol: str) -> dict | None:
        """获取股票行情详情"""
        return _provider.market.get_stock_quote_detail(symbol)

    def get_stock_pankou(self, symbol: str) -> dict | None:
        """获取股票盘口数据"""
        return _provider.market.get_stock_pankou(symbol)

    def get_daily_history(
        self,
        symbol: str,
        *,
        count: int = 240,
        as_of: date | None = None,
    ) -> list[dict]:
        """获取日线历史数据"""
        return _provider.market.get_daily_history(symbol, count=count, as_of=as_of)

    def get_kline_history(
        self,
        symbol: str,
        *,
        period: str = "day",
        count: int = 240,
        as_of: date | None = None,
        is_index: bool = False,
    ) -> list[dict]:
        """获取 K 线历史数据"""
        return _provider.market.get_kline_history(
            symbol,
            period=period,
            count=count,
            as_of=as_of,
            is_index=is_index,
        )

    def get_recent_financials(
        self,
        symbol: str,
        *,
        count: int = 8,
    ) -> list[dict]:
        """获取最近的财务数据"""
        return _provider.market.get_recent_financials(symbol, count=count)

    def get_stock_reports(
        self,
        symbol: str,
        *,
        count: int = 20,
    ) -> list[dict]:
        """获取研究报告"""
        return _provider.market.get_stock_reports(symbol, limit=count)

    def get_stock_earning_forecasts(
        self,
        symbol: str,
        *,
        count: int = 3,
    ) -> list[dict]:
        """获取盈利预测"""
        return _provider.market.get_stock_earning_forecasts(symbol, limit=count)

    def load_stock_basics_cache(
        self,
        symbols: list[str] | None = None,
        *,
        allow_stale: bool = True,
    ) -> list[dict]:
        """从缓存加载股票基础信息"""
        # 保持与原实现一致，直接调用 utils 缓存加载器
        from etl.utils.stock_basics_cache import load_stock_basics_cache as _load_stock_basics_cache
        return _load_stock_basics_cache(symbols, allow_stale=allow_stale)

    def market_from_symbol(self, symbol: str) -> str:
        """从股票代码推断市场"""
        return _provider.market.market_from_symbol(symbol)

    def normalize_index_symbol(self, symbol: str) -> str:
        """标准化指数代码"""
        return _provider.market.normalize_index_symbol(symbol)
