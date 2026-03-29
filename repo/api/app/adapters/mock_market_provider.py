"""
Mock 市场数据提供者

用于单元测试，不依赖真实的数据源。
"""
from __future__ import annotations

from datetime import date, datetime


class MockMarketDataProvider:
    """
    Mock 市场数据提供者
    
    用于单元测试，返回预定义的测试数据。
    """

    def __init__(self, test_data: dict | None = None):
        """
        初始化 Mock 提供者
        
        Args:
            test_data: 测试数据字典，可以预设返回值
        """
        self._test_data = test_data or {}

    def get_stock_basic(
        self,
        symbols: list[str] | None = None,
        *,
        force_refresh: bool = False,
        allow_stale_cache: bool = True,
    ) -> list[dict]:
        """返回 Mock 股票基础信息"""
        if "stock_basic" in self._test_data:
            data = self._test_data["stock_basic"]
            if symbols:
                return [item for item in data if item.get("symbol") in symbols]
            return data
        
        # 默认测试数据
        default_stocks = [
            {
                "symbol": "600000.SH",
                "name": "浦发银行",
                "market": "A",
                "sector": "银行",
            },
            {
                "symbol": "000001.SZ",
                "name": "平安银行",
                "market": "A",
                "sector": "银行",
            },
        ]
        
        if symbols:
            return [item for item in default_stocks if item.get("symbol") in symbols]
        return default_stocks

    def get_stock_quote(self, symbol: str) -> dict | None:
        """返回 Mock 实时行情"""
        if "stock_quote" in self._test_data:
            return self._test_data["stock_quote"].get(symbol)
        
        return {
            "symbol": symbol,
            "current": 10.50,
            "change": 0.50,
            "percent": 5.0,
            "open": 10.00,
            "high": 10.80,
            "low": 9.90,
            "last_close": 10.00,
            "volume": 1000000,
            "amount": 10500000,
            "timestamp": datetime.now(),
        }

    def get_stock_quote_detail(self, symbol: str) -> dict | None:
        """返回 Mock 行情详情"""
        if "stock_quote_detail" in self._test_data:
            return self._test_data["stock_quote_detail"].get(symbol)
        
        return {
            "pe_ttm": 15.5,
            "pb": 1.2,
            "ps_ttm": 2.5,
            "pcf": 8.0,
            "market_cap": 100000000000,
            "float_market_cap": 80000000000,
            "dividend_yield": 3.5,
            "volume_ratio": 1.2,
            "lot_size": 100,
        }

    def get_stock_pankou(self, symbol: str) -> dict | None:
        """返回 Mock 盘口数据"""
        if "stock_pankou" in self._test_data:
            return self._test_data["stock_pankou"].get(symbol)
        
        return {
            "diff": 100,
            "ratio": 0.5,
            "timestamp": datetime.now(),
            "bids": [
                {"level": 1, "price": 10.49, "volume": 1000},
                {"level": 2, "price": 10.48, "volume": 2000},
            ],
            "asks": [
                {"level": 1, "price": 10.50, "volume": 1500},
                {"level": 2, "price": 10.51, "volume": 2500},
            ],
        }

    def get_daily_history(
        self,
        symbol: str,
        *,
        count: int = 240,
        as_of: date | None = None,
    ) -> list[dict]:
        """返回 Mock 日线历史数据"""
        if "daily_history" in self._test_data:
            return self._test_data["daily_history"].get(symbol, [])
        
        # 生成简单的测试数据
        result = []
        base_date = as_of or date.today()
        for i in range(min(count, 10)):
            result.append({
                "symbol": symbol,
                "date": date(base_date.year, base_date.month, max(1, base_date.day - i)),
                "open": 10.0 + i * 0.1,
                "high": 10.5 + i * 0.1,
                "low": 9.5 + i * 0.1,
                "close": 10.0 + i * 0.1,
                "volume": 1000000 + i * 10000,
            })
        return result[::-1]

    def get_kline_history(
        self,
        symbol: str,
        *,
        period: str = "day",
        count: int = 240,
        as_of: date | None = None,
    ) -> list[dict]:
        """返回 Mock K 线历史数据"""
        if "kline_history" in self._test_data:
            return self._test_data["kline_history"].get(symbol, [])
        
        # 复用 daily_history 的逻辑
        return self.get_daily_history(symbol, count=count, as_of=as_of)

    def get_recent_financials(
        self,
        symbol: str,
        *,
        count: int = 8,
    ) -> list[dict]:
        """返回 Mock 财务数据"""
        if "recent_financials" in self._test_data:
            return self._test_data["recent_financials"].get(symbol, [])
        
        return [
            {
                "period": "2024Q4",
                "revenue": 1000000000,
                "net_income": 100000000,
                "cash_flow": 80000000,
                "roe": 15.5,
                "debt_ratio": 0.45,
            },
            {
                "period": "2024Q3",
                "revenue": 950000000,
                "net_income": 95000000,
                "cash_flow": 75000000,
                "roe": 14.8,
                "debt_ratio": 0.48,
            },
        ]

    def get_stock_reports(
        self,
        symbol: str,
        *,
        count: int = 20,
    ) -> list[dict]:
        """返回 Mock 研究报告"""
        if "stock_reports" in self._test_data:
            return self._test_data["stock_reports"].get(symbol, [])
        
        return [
            {
                "title": "2024年度投资价值分析",
                "institution": "某证券",
                "rating": "买入",
                "published_at": datetime.now(),
                "link": "https://example.com/report1",
            }
        ]

    def get_stock_earning_forecasts(
        self,
        symbol: str,
        *,
        count: int = 3,
    ) -> list[dict]:
        """返回 Mock 盈利预测"""
        if "earning_forecasts" in self._test_data:
            return self._test_data["earning_forecasts"].get(symbol, [])
        
        return [
            {
                "year": "2025",
                "eps": 1.50,
                "pe": 15.0,
            },
            {
                "year": "2026",
                "eps": 1.80,
                "pe": 13.5,
            },
        ]

    def load_stock_basics_cache(
        self,
        symbols: list[str] | None = None,
        *,
        allow_stale: bool = True,
    ) -> list[dict]:
        """从缓存加载股票基础信息"""
        # Mock 实现直接调用 get_stock_basic
        return self.get_stock_basic(symbols, allow_stale_cache=allow_stale)

    def market_from_symbol(self, symbol: str) -> str:
        """从股票代码推断市场"""
        if symbol.endswith(".SH") or symbol.endswith(".SZ") or symbol.endswith(".BJ"):
            return "A"
        if symbol.endswith(".HK"):
            return "HK"
        if symbol.endswith(".US"):
            return "US"
        return "A"

    def normalize_index_symbol(self, symbol: str) -> str:
        """标准化指数代码"""
        # 简单实现
        return symbol.upper().strip()
