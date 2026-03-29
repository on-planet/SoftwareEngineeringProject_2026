"""测试数据库连接池优化"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from etl.utils.db_pool import (
    create_session,
    dispose_all_engines,
    get_engine,
    get_session_factory,
)


class TestDbPoolOptimization(unittest.TestCase):
    """测试数据库连接池管理优化"""

    def setUp(self):
        """清理缓存的引擎"""
        dispose_all_engines()

    def tearDown(self):
        """清理缓存的引擎"""
        dispose_all_engines()

    @patch("etl.utils.db_pool.create_engine")
    def test_get_engine_returns_singleton(self, mock_create_engine):
        """测试相同配置返回同一个引擎实例"""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        url = "postgresql://test:test@localhost/test"
        engine1 = get_engine(url, pool_size=5, max_overflow=5)
        engine2 = get_engine(url, pool_size=5, max_overflow=5)

        # 应该只创建一次引擎
        self.assertEqual(mock_create_engine.call_count, 1)
        self.assertIs(engine1, engine2)

    @patch("etl.utils.db_pool.create_engine")
    def test_get_engine_different_config_creates_new_engine(self, mock_create_engine):
        """测试不同配置创建不同的引擎实例"""
        mock_engine1 = MagicMock()
        mock_engine2 = MagicMock()
        mock_create_engine.side_effect = [mock_engine1, mock_engine2]

        url = "postgresql://test:test@localhost/test"
        engine1 = get_engine(url, pool_size=5, max_overflow=5)
        engine2 = get_engine(url, pool_size=10, max_overflow=10)

        # 应该创建两次引擎（配置不同）
        self.assertEqual(mock_create_engine.call_count, 2)
        self.assertIsNot(engine1, engine2)

    @patch("etl.utils.db_pool.create_engine")
    def test_get_session_factory_returns_singleton(self, mock_create_engine):
        """测试相同配置返回同一个 Session 工厂"""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        url = "postgresql://test:test@localhost/test"
        factory1 = get_session_factory(url, pool_size=5)
        factory2 = get_session_factory(url, pool_size=5)

        # 应该只创建一次引擎
        self.assertEqual(mock_create_engine.call_count, 1)
        # Session 工厂应该是同一个实例
        self.assertIs(factory1, factory2)

    @patch("etl.utils.db_pool.create_engine")
    def test_create_session_uses_shared_pool(self, mock_create_engine):
        """测试创建多个 Session 使用共享连接池"""
        mock_engine = MagicMock()
        mock_session = MagicMock()
        mock_create_engine.return_value = mock_engine

        url = "postgresql://test:test@localhost/test"
        
        with patch("etl.utils.db_pool.get_session_factory") as mock_factory:
            mock_factory.return_value = lambda: mock_session
            session1 = create_session(url)
            session2 = create_session(url)

            # 应该使用同一个工厂
            self.assertEqual(mock_factory.call_count, 2)

    @patch("etl.utils.db_pool.create_engine")
    def test_dispose_all_engines_clears_cache(self, mock_create_engine):
        """测试 dispose_all_engines 清理所有缓存"""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        url = "postgresql://test:test@localhost/test"
        get_engine(url)
        
        dispose_all_engines()
        
        # 应该调用 dispose
        mock_engine.dispose.assert_called_once()
        
        # 再次获取应该创建新引擎
        get_engine(url)
        self.assertEqual(mock_create_engine.call_count, 2)


if __name__ == "__main__":
    unittest.main()
