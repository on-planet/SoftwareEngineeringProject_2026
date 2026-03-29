"""测试市场数据适配器"""
from __future__ import annotations

import unittest

from app.adapters.factory import get_market_data_adapter, set_market_data_adapter
from app.adapters.market_data_adapter import MarketDataAdapter
from app.adapters.mock_market_provider import MockMarketDataProvider


class TestMarketDataAdapter(unittest.TestCase):
    """测试市场数据适配器解耦效果"""

    def setUp(self):
        """设置测试环境"""
        # 使用 Mock 提供者进行测试
        test_data = {
            "stock_basic": [
                {
                    "symbol": "600000.SH",
                    "name": "测试股票",
                    "market": "A",
                    "sector": "测试行业",
                }
            ],
            "stock_quote": {
                "600000.SH": {
                    "symbol": "600000.SH",
                    "current": 12.50,
                    "change": 0.50,
                    "percent": 4.17,
                }
            },
        }
        mock_provider = MockMarketDataProvider(test_data)
        mock_adapter = MarketDataAdapter(mock_provider)
        set_market_data_adapter(mock_adapter)

    def test_get_stock_basic_through_adapter(self):
        """测试通过适配器获取股票基础信息"""
        adapter = get_market_data_adapter()
        result = adapter.get_stock_basic(["600000.SH"])
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["symbol"], "600000.SH")
        self.assertEqual(result[0]["name"], "测试股票")
        self.assertEqual(result[0]["sector"], "测试行业")

    def test_get_stock_quote_through_adapter(self):
        """测试通过适配器获取实时行情"""
        adapter = get_market_data_adapter()
        result = adapter.get_stock_quote("600000.SH")
        
        self.assertIsInstance(result, dict)
        self.assertEqual(result.get("symbol"), "600000.SH")
        self.assertEqual(result.get("current"), 12.50)
        self.assertEqual(result.get("percent"), 4.17)

    def test_market_from_symbol_through_adapter(self):
        """测试通过适配器推断市场"""
        adapter = get_market_data_adapter()
        
        self.assertEqual(adapter.market_from_symbol("600000.SH"), "A")
        self.assertEqual(adapter.market_from_symbol("00700.HK"), "HK")
        self.assertEqual(adapter.market_from_symbol("AAPL.US"), "US")

    def test_adapter_is_singleton(self):
        """测试适配器是单例模式"""
        adapter1 = get_market_data_adapter()
        adapter2 = get_market_data_adapter()
        
        self.assertIs(adapter1, adapter2)

    def test_can_switch_provider(self):
        """测试可以切换数据提供者"""
        # 创建新的 Mock 提供者
        new_test_data = {
            "stock_basic": [
                {
                    "symbol": "000001.SZ",
                    "name": "新测试股票",
                    "market": "A",
                    "sector": "新行业",
                }
            ]
        }
        new_provider = MockMarketDataProvider(new_test_data)
        new_adapter = MarketDataAdapter(new_provider)
        set_market_data_adapter(new_adapter)
        
        result = new_adapter.get_stock_basic(["000001.SZ"])
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "新测试股票")

    def test_adapter_provides_all_required_methods(self):
        """测试适配器提供所有必需的方法"""
        adapter = get_market_data_adapter()
        
        required_methods = [
            "get_stock_basic",
            "get_stock_quote",
            "get_stock_quote_detail",
            "get_stock_pankou",
            "get_daily_history",
            "get_kline_history",
            "get_recent_financials",
            "get_stock_reports",
            "get_stock_earning_forecasts",
            "load_stock_basics_cache",
            "market_from_symbol",
            "normalize_index_symbol",
        ]
        
        for method_name in required_methods:
            self.assertTrue(
                hasattr(adapter, method_name),
                f"适配器缺少方法: {method_name}"
            )
            self.assertTrue(
                callable(getattr(adapter, method_name)),
                f"适配器的 {method_name} 不是可调用对象"
            )


if __name__ == "__main__":
    unittest.main()
