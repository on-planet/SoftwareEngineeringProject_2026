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
        ), patch("app.services.live_market_service.set_json"), patch(
            "app.services.live_market_service._queue_background_profile_refresh_for_rows"
        ):
            items, total = list_live_stocks(market="HK", limit=10, offset=0, sort="asc")

        self.assertEqual(total, 120)
        self.assertEqual(len(items), 10)
        self.assertEqual(items[0]["symbol"], "00001.HK")

    def test_market_list_stays_local_only_when_cache_is_insufficient(self) -> None:
        fallback_rows = [
            {"symbol": "00700.HK", "name": "Tencent", "market": "HK", "sector": "Tech"},
        ]
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._fallback_stock_rows",
            return_value=fallback_rows,
        ), patch("app.services.live_market_service.set_json"), patch(
            "app.services.live_market_service._queue_background_profile_refresh_for_rows"
        ):
            items, total = list_live_stocks(market="HK", limit=10, offset=0, sort="asc")

        self.assertEqual(total, 1)
        self.assertEqual([item["symbol"] for item in items], ["00700.HK"])

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
            "app.services.live_market_service.load_stock_basics_cache",
            return_value=local_rows,
        ), patch("app.services.live_market_service.set_json") as set_json, patch(
            "app.services.live_market_service._queue_background_profile_refresh_for_rows"
        ):
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
            "app.services.live_market_service.load_stock_basics_cache",
            return_value=[],
        ), patch("app.services.live_market_service.set_json") as set_json, patch(
            "app.services.live_market_service._queue_background_profile_refresh_for_rows"
        ):
            items, total = list_live_stocks(market="A", limit=10, offset=0, sort="asc")

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["name"], "平安银行")
        self.assertEqual(items[0]["sector"], "货币金融服务")
        set_json.assert_called_once()

    def test_market_list_filters_out_non_equity_sh_symbols(self) -> None:
        fallback_rows = [
            {"symbol": "000001.SH", "name": "INDEX", "market": "A", "sector": "Unknown"},
            {"symbol": "113001.SH", "name": "BOND", "market": "A", "sector": "Unknown"},
            {"symbol": "600000.SH", "name": "SPDB", "market": "A", "sector": "Banks"},
            {"symbol": "688001.SH", "name": "STAR", "market": "A", "sector": "Tech"},
            {"symbol": "002001.SZ", "name": "SZ", "market": "A", "sector": "Industrial"},
            {"symbol": "301001.SZ", "name": "GEM", "market": "A", "sector": "Healthcare"},
        ]
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._fallback_stock_rows",
            return_value=fallback_rows,
        ), patch("app.services.live_market_service.set_json"), patch(
            "app.services.live_market_service._queue_background_profile_refresh_for_rows"
        ):
            items, total = list_live_stocks(market="A", limit=10, offset=0, sort="asc")

        self.assertEqual(total, 4)
        self.assertEqual([item["symbol"] for item in items], ["002001.SZ", "301001.SZ", "600000.SH", "688001.SH"])

    def test_cached_market_list_queues_background_refresh_for_unknown_sector_rows(self) -> None:
        cached_payload = {
            "items": [
                {"symbol": "000001.SZ", "name": "000001.SZ", "market": "A", "sector": "Unknown"},
            ],
            "total": 1,
        }
        with patch("app.services.live_market_service.get_json", return_value=cached_payload), patch(
            "app.services.live_market_service.load_stock_basics_cache",
            return_value=[],
        ), patch("app.services.live_market_service._queue_background_profile_refresh_for_rows") as queue_refresh:
            list_live_stocks(market="A", limit=10, offset=0, sort="asc")

        queue_refresh.assert_called_once()

    def test_cached_market_list_still_calls_refresh_helper_for_known_rows(self) -> None:
        cached_payload = {
            "items": [
                {"symbol": "000001.SZ", "name": "PingAn", "market": "A", "sector": "Financials"},
            ],
            "total": 1,
        }
        with patch("app.services.live_market_service.get_json", return_value=cached_payload), patch(
            "app.services.live_market_service.load_stock_basics_cache",
            return_value=[],
        ), patch("app.services.live_market_service._queue_background_profile_refresh_for_rows") as queue_refresh:
            list_live_stocks(market="A", limit=10, offset=0, sort="asc")

        queue_refresh.assert_called_once()


if __name__ == "__main__":
    unittest.main()
