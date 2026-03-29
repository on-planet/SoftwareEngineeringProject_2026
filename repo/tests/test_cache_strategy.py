"""测试缓存策略"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.core.cache_strategy import (
    CacheLevel,
    get_cache_config,
    get_ttl_for_cache_level,
    get_ttl_for_data_type,
    should_use_memory_cache,
)
from app.core.typed_cache import TypedCache, cache_with_type


class TestCacheStrategy(unittest.TestCase):
    """测试缓存策略配置"""

    def test_realtime_data_has_short_ttl(self):
        """测试实时数据使用短 TTL"""
        ttl = get_ttl_for_data_type("stock_quote")
        self.assertEqual(ttl, 5)  # 5秒
        
        ttl = get_ttl_for_data_type("stock_pankou")
        self.assertEqual(ttl, 5)

    def test_financial_data_has_long_ttl(self):
        """测试财报数据使用长 TTL"""
        ttl = get_ttl_for_data_type("financial_report")
        self.assertEqual(ttl, 86400)  # 1天
        
        ttl = get_ttl_for_data_type("stock_research")
        self.assertEqual(ttl, 86400)

    def test_basic_info_has_permanent_ttl(self):
        """测试基础信息使用永久 TTL"""
        ttl = get_ttl_for_data_type("stock_basic")
        self.assertEqual(ttl, 604800)  # 7天

    def test_realtime_data_uses_memory_cache(self):
        """测试实时数据优先使用内存缓存"""
        self.assertTrue(should_use_memory_cache("stock_quote"))
        self.assertTrue(should_use_memory_cache("stock_pankou"))
        self.assertTrue(should_use_memory_cache("intraday_kline"))

    def test_long_term_data_not_prefer_memory_cache(self):
        """测试长期数据不优先使用内存缓存"""
        self.assertFalse(should_use_memory_cache("financial_report"))
        self.assertFalse(should_use_memory_cache("stock_basic"))

    def test_get_cache_config(self):
        """测试获取完整缓存配置"""
        config = get_cache_config("stock_quote")
        self.assertEqual(config.ttl, 5)
        self.assertEqual(config.level, CacheLevel.REALTIME)
        self.assertIn("实时", config.description)

    def test_unknown_data_type_uses_default(self):
        """测试未知数据类型使用默认配置"""
        ttl = get_ttl_for_data_type("unknown_type")
        self.assertEqual(ttl, 3600)  # 默认1小时


class TestTypedCache(unittest.TestCase):
    """测试类型化缓存"""

    def setUp(self):
        """设置测试环境"""
        # Mock Redis 客户端
        self.mock_redis = MagicMock()
        self.mock_redis.get.return_value = None
        self.mock_redis.set.return_value = True
        self.mock_redis.delete.return_value = 1

    @patch("app.core.cache.get_redis_client")
    def test_typed_cache_uses_correct_ttl(self, mock_get_redis):
        """测试类型化缓存使用正确的 TTL"""
        mock_get_redis.return_value = self.mock_redis
        
        # 实时数据缓存
        quote_cache = TypedCache("stock_quote")
        self.assertEqual(quote_cache.default_ttl, 5)
        
        # 财报数据缓存
        financial_cache = TypedCache("financial_report")
        self.assertEqual(financial_cache.default_ttl, 86400)

    @patch("app.core.cache.get_redis_client")
    def test_typed_cache_get_or_set(self, mock_get_redis):
        """测试 get_or_set 方法"""
        mock_get_redis.return_value = self.mock_redis
        
        cache = TypedCache("stock_quote")
        
        # 第一次调用，缓存不存在
        factory_called = False
        def factory():
            nonlocal factory_called
            factory_called = True
            return {"symbol": "600000.SH", "price": 10.50}
        
        result = cache.get_or_set("test_key", factory)
        
        self.assertTrue(factory_called)
        self.assertEqual(result["symbol"], "600000.SH")

    @patch("app.core.cache.get_redis_client")
    def test_cache_decorator(self, mock_get_redis):
        """测试缓存装饰器"""
        mock_get_redis.return_value = self.mock_redis
        
        call_count = 0
        
        @cache_with_type("stock_quote")
        def get_stock_price(symbol: str):
            nonlocal call_count
            call_count += 1
            return {"symbol": symbol, "price": 10.50}
        
        # 第一次调用
        result1 = get_stock_price("600000.SH")
        self.assertEqual(call_count, 1)
        
        # 第二次调用（应该从缓存获取）
        # 注意：由于我们 mock 了 Redis，实际不会缓存
        # 这里只是测试装饰器的基本功能
        result2 = get_stock_price("600000.SH")
        self.assertEqual(result1["symbol"], result2["symbol"])


class TestCachePerformance(unittest.TestCase):
    """测试缓存性能"""

    @patch("app.core.cache.get_redis_client")
    def test_memory_cache_size_limit(self, mock_get_redis):
        """测试内存缓存大小限制"""
        from app.core.cache import MAX_MEMORY_CACHE_SIZE, clear_memory_cache
        
        mock_get_redis.return_value = None  # 只使用内存缓存
        
        cache = TypedCache("stock_quote")
        
        # 清空缓存
        clear_memory_cache()
        
        # 写入大量数据
        for i in range(MAX_MEMORY_CACHE_SIZE + 100):
            cache.set(f"key_{i}", {"value": i})
        
        # 验证缓存大小不超过限制
        from app.core.cache import get_cache_stats
        stats = get_cache_stats()
        
        self.assertLessEqual(
            stats["memory_cache"]["size"],
            MAX_MEMORY_CACHE_SIZE,
            "内存缓存大小应该不超过限制"
        )

    @patch("app.core.cache.get_redis_client")
    def test_cache_stats(self, mock_get_redis):
        """测试缓存统计"""
        from app.core.cache import clear_memory_cache, get_cache_stats
        
        mock_get_redis.return_value = None
        
        # 清空缓存和统计
        clear_memory_cache()
        
        cache = TypedCache("stock_quote")
        
        # 写入数据
        cache.set("test_key", {"value": 123})
        
        # 读取数据（命中）
        cache.get("test_key")
        
        # 读取不存在的数据（未命中）
        cache.get("nonexistent_key")
        
        # 获取统计
        stats = get_cache_stats()
        
        self.assertGreater(stats["memory_cache"]["hits"], 0)
        self.assertGreater(stats["memory_cache"]["misses"], 0)
        self.assertGreater(stats["memory_cache"]["sets"], 0)


if __name__ == "__main__":
    unittest.main()
