"""
实时市场数据远程访问

通过数据适配层访问市场数据，解耦 API 和 ETL 层的直接依赖。

优化说明：
- 不再直接导入 ETL 层的 fetchers 和 transformers
- 通过适配器模式访问数据，便于测试和替换实现
- 支持运行时切换不同的数据源
"""
from __future__ import annotations

from datetime import date

from app.adapters.factory import get_market_data_adapter


def get_cached_stock_basic(
    symbols: list[str] | None = None,
    *,
    force_refresh: bool = False,
    allow_stale_cache: bool = True,
) -> list[dict]:
    """获取股票基础信息（带缓存）"""
    adapter = get_market_data_adapter()
    return adapter.get_stock_basic(
        symbols,
        force_refresh=force_refresh,
        allow_stale_cache=allow_stale_cache,
    )


def load_stock_basics_cache(
    symbols: list[str] | None = None,
    *,
    allow_stale: bool = True,
) -> list[dict]:
    """从缓存加载股票基础信息"""
    adapter = get_market_data_adapter()
    return adapter.load_stock_basics_cache(symbols, allow_stale=allow_stale)


def get_daily_history(symbol: str, *, count: int = 240, as_of: date | None = None) -> list[dict]:
    """获取日线历史数据"""
    adapter = get_market_data_adapter()
    return adapter.get_daily_history(symbol, count=count, as_of=as_of)


def get_kline_history(
    symbol: str,
    *,
    period: str = "day",
    count: int = 240,
    as_of: date | None = None,
    is_index: bool = False,
) -> list[dict]:
    """获取 K 线历史数据"""
    adapter = get_market_data_adapter()
    return adapter.get_kline_history(symbol, period=period, count=count, as_of=as_of)


def get_recent_financials(symbol: str, *, count: int = 8) -> list[dict]:
    """获取最近的财务数据"""
    adapter = get_market_data_adapter()
    return adapter.get_recent_financials(symbol, count=count)


def get_stock_quote(symbol: str) -> dict:
    """获取股票实时行情"""
    adapter = get_market_data_adapter()
    return adapter.get_stock_quote(symbol) or {}


def get_stock_quote_detail(symbol: str) -> dict:
    """获取股票行情详情"""
    adapter = get_market_data_adapter()
    return adapter.get_stock_quote_detail(symbol) or {}


def get_stock_pankou(symbol: str) -> dict:
    """获取股票盘口数据"""
    adapter = get_market_data_adapter()
    return adapter.get_stock_pankou(symbol) or {}


def get_stock_reports(symbol: str, *, limit: int = 10) -> list[dict]:
    """获取研究报告"""
    adapter = get_market_data_adapter()
    return adapter.get_stock_reports(symbol, count=limit)


def get_stock_earning_forecasts(symbol: str, *, limit: int = 10) -> list[dict]:
    """获取盈利预测"""
    adapter = get_market_data_adapter()
    return adapter.get_stock_earning_forecasts(symbol, count=limit)


def normalize_index_symbol(symbol: str) -> str:
    """标准化指数代码"""
    adapter = get_market_data_adapter()
    return adapter.normalize_index_symbol(symbol)


def market_from_symbol(symbol: str) -> str:
    """从股票代码推断市场"""
    adapter = get_market_data_adapter()
    return adapter.market_from_symbol(symbol)
