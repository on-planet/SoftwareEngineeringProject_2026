from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.fetchers.market_client import _can_apply_baostock_sector, get_stock_basic, warm_stock_basic_enrichment


class MarketSectorSourceTests(unittest.TestCase):
    def test_baostock_sector_only_applies_to_a_share_markets(self) -> None:
        self.assertTrue(_can_apply_baostock_sector("600000.SH"))
        self.assertTrue(_can_apply_baostock_sector("000001.SZ"))
        self.assertTrue(_can_apply_baostock_sector("430001.BJ"))
        self.assertFalse(_can_apply_baostock_sector("00700.HK"))
        self.assertFalse(_can_apply_baostock_sector("AAPL.US"))

    def test_hk_sector_is_not_overwritten_by_baostock(self) -> None:
        snowball_rows = [
            {"symbol": "00700.HK", "name": "Tencent", "market": "HK", "sector": "Communication Services"},
            {"symbol": "600000.SH", "name": "SPDB", "market": "A", "sector": "Banks"},
        ]
        baostock_rows = [
            {"symbol": "00700.HK", "sector": "ShouldNotApply"},
            {"symbol": "600000.SH", "sector": "货币金融服务"},
        ]
        with patch("etl.fetchers.market_client.HK_PROFILE_ENRICH_ENABLED", False), patch(
            "etl.fetchers.market_client.load_stock_basics_cache", return_value=[]
        ), patch(
            "etl.fetchers.market_client.load_baostock_industry_cache",
            return_value=[],
        ), patch("etl.fetchers.market_client.list_stock_rows", return_value=[]), patch(
            "etl.fetchers.market_client.sb_get_stock_basics",
            return_value=snowball_rows,
        ), patch("etl.fetchers.market_client.get_stock_industry", return_value=baostock_rows), patch(
            "etl.fetchers.market_client.save_stock_basics_cache"
        ), patch("etl.fetchers.market_client.save_baostock_industry_cache"):
            rows = get_stock_basic(["00700.HK", "600000.SH"], force_refresh=True, allow_stale_cache=False)

        by_symbol = {row["symbol"]: row for row in rows}
        self.assertEqual(by_symbol["00700.HK"]["sector"], "Communication Services")
        self.assertEqual(by_symbol["600000.SH"]["sector"], "货币金融服务")

    def test_a_share_name_can_be_filled_from_baostock(self) -> None:
        snowball_rows = [
            {"symbol": "000001.SZ", "name": "000001.SZ", "market": "A", "sector": "Banks"},
        ]
        baostock_rows = [
            {"symbol": "000001.SZ", "name": "平安银行", "sector": "货币金融服务"},
        ]
        with patch("etl.fetchers.market_client.HK_PROFILE_ENRICH_ENABLED", False), patch(
            "etl.fetchers.market_client.load_stock_basics_cache", return_value=[]
        ), patch(
            "etl.fetchers.market_client.load_baostock_industry_cache",
            return_value=[],
        ), patch("etl.fetchers.market_client.list_stock_rows", return_value=[]), patch(
            "etl.fetchers.market_client.sb_get_stock_basics",
            return_value=snowball_rows,
        ), patch("etl.fetchers.market_client.get_stock_industry", return_value=baostock_rows), patch(
            "etl.fetchers.market_client.save_stock_basics_cache"
        ), patch("etl.fetchers.market_client.save_baostock_industry_cache"):
            rows = get_stock_basic(["000001.SZ"], force_refresh=True, allow_stale_cache=False)

        self.assertEqual(rows[0]["name"], "平安银行")
        self.assertEqual(rows[0]["sector"], "货币金融服务")

    def test_cached_baostock_enrichment_avoids_online_query(self) -> None:
        snowball_rows = [
            {"symbol": "000001.SZ", "name": "000001.SZ", "market": "A", "sector": "Unknown"},
        ]
        cached_baostock_rows = [
            {"symbol": "000001.SZ", "name": "平安银行", "sector": "货币金融服务"},
        ]
        with patch("etl.fetchers.market_client.HK_PROFILE_ENRICH_ENABLED", False), patch(
            "etl.fetchers.market_client.load_stock_basics_cache", return_value=[]
        ), patch(
            "etl.fetchers.market_client.load_baostock_industry_cache",
            return_value=cached_baostock_rows,
        ), patch("etl.fetchers.market_client.list_stock_rows", return_value=[]), patch(
            "etl.fetchers.market_client.sb_get_stock_basics",
            return_value=snowball_rows,
        ), patch("etl.fetchers.market_client.get_stock_industry") as online_mock, patch(
            "etl.fetchers.market_client.save_stock_basics_cache"
        ):
            rows = get_stock_basic(["000001.SZ"], force_refresh=True, allow_stale_cache=False)

        online_mock.assert_not_called()
        self.assertEqual(rows[0]["name"], "平安银行")
        self.assertEqual(rows[0]["sector"], "货币金融服务")

    def test_new_a_share_symbol_triggers_online_baostock_refresh(self) -> None:
        stock_rows = [
            {"symbol": "000001.SZ", "name": "000001.SZ", "market": "A", "sector": "Unknown"},
            {"symbol": "600000.SH", "name": "浦发银行", "market": "A", "sector": "货币金融服务"},
        ]
        fresh_baostock_rows = [
            {"symbol": "000001.SZ", "name": "平安银行", "sector": "货币金融服务"},
            {"symbol": "600000.SH", "name": "浦发银行", "sector": "货币金融服务"},
        ]
        with patch("etl.fetchers.market_client.HK_PROFILE_ENRICH_ENABLED", False), patch(
            "etl.fetchers.market_client.load_stock_basics_cache", return_value=stock_rows
        ), patch(
            "etl.fetchers.market_client.load_baostock_industry_cache",
            return_value=[fresh_baostock_rows[1]],
        ), patch("etl.fetchers.market_client.get_stock_industry", return_value=fresh_baostock_rows) as online_mock, patch(
            "etl.fetchers.market_client.save_baostock_industry_cache"
        ) as save_mock:
            count = warm_stock_basic_enrichment()

        online_mock.assert_called_once()
        save_mock.assert_called_once()
        self.assertEqual(count, len(fresh_baostock_rows))

    def test_cached_stock_basics_rows_are_enriched_by_cached_baostock(self) -> None:
        cached_stock_rows = [
            {"symbol": "000001.SZ", "name": "000001.SZ", "market": "A", "sector": "Unknown"},
        ]
        cached_baostock_rows = [
            {"symbol": "000001.SZ", "name": "平安银行", "sector": "货币金融服务"},
        ]
        with patch("etl.fetchers.market_client.HK_PROFILE_ENRICH_ENABLED", False), patch(
            "etl.fetchers.market_client.load_stock_basics_cache", return_value=cached_stock_rows
        ), patch(
            "etl.fetchers.market_client.load_baostock_industry_cache",
            return_value=cached_baostock_rows,
        ), patch("etl.fetchers.market_client.save_stock_basics_cache") as save_mock:
            rows = get_stock_basic(["000001.SZ"], force_refresh=False, allow_stale_cache=True)

        save_mock.assert_called()
        self.assertEqual(rows[0]["name"], "平安银行")
        self.assertEqual(rows[0]["sector"], "货币金融服务")


if __name__ == "__main__":
    unittest.main()
