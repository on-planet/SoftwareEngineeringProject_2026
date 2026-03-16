from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from app.services.live_market_service import list_live_stocks


class StockPoolLocalFallbackTests(unittest.TestCase):
    def test_market_list_uses_local_cache_without_remote_when_sufficient(self) -> None:
        fallback_rows = [
            {"symbol": f"{idx:05d}.HK", "name": f"HK-{idx}", "market": "HK", "sector": "Unknown"}
            for idx in range(1, 121)
        ]
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._fallback_stock_rows",
            return_value=fallback_rows,
        ), patch("app.services.live_market_service.get_market_stock_pool") as market_pool, patch(
            "app.services.live_market_service.search_stocks"
        ) as search_stocks, patch("app.services.live_market_service.set_json"):
            items, total = list_live_stocks(market="HK", limit=10, offset=0, sort="asc")

        market_pool.assert_not_called()
        search_stocks.assert_not_called()
        self.assertEqual(total, 100)
        self.assertEqual(len(items), 10)
        self.assertEqual(items[0]["symbol"], "00001.HK")

    def test_market_list_uses_remote_topup_when_local_cache_is_insufficient(self) -> None:
        fallback_rows = [
            {"symbol": "00700.HK", "name": "Tencent", "market": "HK", "sector": "Tech"},
        ]
        remote_rows = [
            {"symbol": "00005.HK", "name": "HSBC", "market": "HK", "sector": "Financials"},
        ]
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._fallback_stock_rows",
            return_value=fallback_rows,
        ), patch(
            "app.services.live_market_service.get_market_stock_pool",
            return_value=remote_rows,
        ) as market_pool, patch("app.services.live_market_service.set_json"):
            items, total = list_live_stocks(market="HK", limit=10, offset=0, sort="asc")

        market_pool.assert_called_once()
        self.assertEqual(total, 2)
        self.assertEqual([item["symbol"] for item in items], ["00005.HK", "00700.HK"])

    def test_cached_market_list_is_hydrated_from_local_basics(self) -> None:
        cached_payload = {
            "items": [
                {"symbol": "000001.SZ", "name": "000001.SZ", "market": "A", "sector": "Unknown"},
            ],
            "total": 1,
        }
        local_rows = [
            {"symbol": "000001.SZ", "name": "平安银行", "market": "A", "sector": "货币金融服务"},
        ]
        with patch("app.services.live_market_service.get_json", return_value=cached_payload), patch(
            "app.services.live_market_service.get_cached_stock_basic",
            return_value=local_rows,
        ), patch("app.services.live_market_service.set_json") as set_json:
            items, total = list_live_stocks(market="A", limit=10, offset=0, sort="asc")

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["name"], "平安银行")
        self.assertEqual(items[0]["sector"], "货币金融服务")
        set_json.assert_called_once()

    def test_cached_market_list_is_hydrated_from_profile_cache(self) -> None:
        cached_payload = {
            "items": [
                {"symbol": "000001.SZ", "name": "000001.SZ", "market": "A", "sector": "Unknown"},
            ],
            "total": 1,
        }
        profile_cache = {
            "symbol": "000001.SZ",
            "name": "平安银行",
            "market": "A",
            "sector": "货币金融服务",
            "quote": {"current": 10.91},
        }
        with patch("app.services.live_market_service.get_json", side_effect=[cached_payload, profile_cache]), patch(
            "app.services.live_market_service.get_cached_stock_basic",
            return_value=[],
        ), patch("app.services.live_market_service.set_json") as set_json:
            items, total = list_live_stocks(market="A", limit=10, offset=0, sort="asc")

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["name"], "平安银行")
        self.assertEqual(items[0]["sector"], "货币金融服务")
        set_json.assert_called_once()


if __name__ == "__main__":
    unittest.main()
