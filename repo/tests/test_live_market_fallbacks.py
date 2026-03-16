from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from app.services.live_market_service import (
    _has_identity_signal,
    _quote_from_daily_rows,
    get_live_financials,
    get_live_fundamental,
    get_live_kline,
    get_live_stock_overview_profile,
    get_live_stock_profile,
    get_live_stock_profile_extras,
)


class LiveMarketFallbackTests(unittest.TestCase):
    def test_identity_signal_requires_name_and_sector(self) -> None:
        self.assertFalse(_has_identity_signal({"symbol": "000001.SZ", "name": "000001.SZ", "sector": "Unknown"}))
        self.assertFalse(_has_identity_signal({"symbol": "000001.SZ", "name": "平安银行", "sector": "Unknown"}))
        self.assertTrue(_has_identity_signal({"symbol": "000001.SZ", "name": "平安银行", "sector": "货币金融服务"}))

    def test_quote_from_daily_rows_returns_empty_without_valid_dates(self) -> None:
        payload = _quote_from_daily_rows("00700.HK", [])
        self.assertEqual(payload, {})

    def test_quote_from_daily_rows_builds_snapshot(self) -> None:
        rows = [
            SimpleNamespace(date=date(2026, 3, 15), open=520.0, high=530.0, low=518.0, close=528.0, volume=3000.0),
            SimpleNamespace(date=date(2026, 3, 15), open=520.0, high=530.0, low=518.0, close=528.0, volume=3000.0),
            SimpleNamespace(date=date(2026, 3, 14), open=510.0, high=515.0, low=505.0, close=512.0, volume=2800.0),
        ]

        payload = _quote_from_daily_rows("700.HK", rows)

        self.assertEqual(payload["symbol"], "00700.HK")
        self.assertEqual(payload["current"], 528.0)
        self.assertEqual(payload["last_close"], 512.0)
        self.assertAlmostEqual(payload["change"], 16.0)
        self.assertAlmostEqual(payload["percent"], 3.125)
        self.assertEqual(payload["open"], 520.0)
        self.assertEqual(payload["volume"], 3000.0)

    def test_get_live_stock_profile_uses_db_snapshot_when_live_quote_missing(self) -> None:
        db_quote = {
            "symbol": "00700.HK",
            "current": 528.0,
            "change": 16.0,
            "percent": 3.125,
            "open": 520.0,
            "high": 530.0,
            "low": 518.0,
            "last_close": 512.0,
            "volume": 3000.0,
            "amount": None,
            "turnover_rate": None,
            "amplitude": None,
            "timestamp": None,
        }
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._fallback_stock_profile",
            return_value={"symbol": "00700.HK", "name": "Tencent", "market": "HK", "sector": "Tech"},
        ), patch("app.services.live_market_service.get_cached_stock_basic", return_value=[]), patch(
            "app.services.live_market_service.get_stock_quote", return_value={}
        ), patch("app.services.live_market_service.get_stock_quote_detail", return_value={}), patch(
            "app.services.live_market_service.get_stock_pankou", return_value={}
        ), patch("app.services.live_market_service._load_db_quote_snapshot", return_value=db_quote), patch(
            "app.services.live_market_service.set_json"
        ):
            payload = get_live_stock_profile("00700.HK")

        self.assertIsNotNone(payload)
        self.assertEqual(payload["quote"]["current"], 528.0)
        self.assertEqual(payload["quote"]["last_close"], 512.0)
        self.assertEqual(payload["name"], "Tencent")

    def test_get_live_stock_profile_can_fill_name_and_sector_from_quote(self) -> None:
        live_quote = {
            "symbol": "000001.SZ",
            "name": "平安银行",
            "sector": "货币金融服务",
            "current": 10.91,
            "change": -0.02,
            "percent": -0.18,
        }
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._fallback_stock_profile",
            return_value={"symbol": "000001.SZ", "name": "000001.SZ", "market": "A", "sector": "Unknown"},
        ), patch("app.services.live_market_service.get_cached_stock_basic", return_value=[]), patch(
            "app.services.live_market_service.get_stock_quote", return_value=live_quote
        ), patch("app.services.live_market_service.get_stock_quote_detail", return_value={}), patch(
            "app.services.live_market_service.get_stock_pankou", return_value={}
        ), patch("app.services.live_market_service.set_json"):
            payload = get_live_stock_profile("000001.SZ")

        self.assertIsNotNone(payload)
        self.assertEqual(payload["name"], "平安银行")
        self.assertEqual(payload["sector"], "货币金融服务")
        self.assertNotIn("name", payload["quote"])
        self.assertNotIn("sector", payload["quote"])

    def test_get_live_kline_prefers_local_daily_rows_for_day_series(self) -> None:
        db_rows = [
            {
                "symbol": "000001.SZ",
                "date": date(2026, 3, 13),
                "open": 10.0,
                "high": 10.5,
                "low": 9.9,
                "close": 10.2,
                "volume": 1000.0,
            },
            {
                "symbol": "000001.SZ",
                "date": date(2026, 3, 14),
                "open": 10.2,
                "high": 10.7,
                "low": 10.1,
                "close": 10.6,
                "volume": 1200.0,
            },
        ]
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._load_db_daily_rows",
            return_value=db_rows,
        ), patch("app.services.live_market_service.get_kline_history") as remote_kline, patch(
            "app.services.live_market_service.set_json"
        ):
            items = get_live_kline("000001.SZ", period="day", limit=60)

        remote_kline.assert_not_called()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[-1].close, 10.6)

    def test_get_live_financials_prefers_local_rows_when_available(self) -> None:
        local_rows = [
            {
                "symbol": "000001.SZ",
                "period": "2025Q4",
                "revenue": 100.0,
                "net_income": 20.0,
                "cash_flow": 30.0,
                "roe": 0.12,
                "debt_ratio": 0.45,
            }
        ]
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._load_db_financial_rows",
            return_value=(local_rows, 1),
        ), patch("app.services.live_market_service.get_recent_financials") as remote_financials, patch(
            "app.services.live_market_service.set_json"
        ):
            items, total = get_live_financials("000001.SZ", limit=12, offset=0, sort="desc")

        remote_financials.assert_not_called()
        self.assertEqual(total, 1)
        self.assertEqual(items[0]["period"], "2025Q4")

    def test_get_live_fundamental_prefers_local_financial_rows(self) -> None:
        local_rows = [
            {
                "symbol": "000001.SZ",
                "period": "2025Q4",
                "revenue": 100.0,
                "net_income": 20.0,
                "cash_flow": 25.0,
                "roe": 0.12,
                "debt_ratio": 0.45,
            },
            {
                "symbol": "000001.SZ",
                "period": "2025Q3",
                "revenue": 80.0,
                "net_income": 16.0,
                "cash_flow": 20.0,
                "roe": 0.1,
                "debt_ratio": 0.43,
            },
        ]
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._load_db_financial_rows",
            return_value=(local_rows, 2),
        ), patch("app.services.live_market_service.get_recent_financials") as remote_financials, patch(
            "app.services.live_market_service.set_json"
        ):
            payload = get_live_fundamental("000001.SZ")

        remote_financials.assert_not_called()
        self.assertIsNotNone(payload)
        self.assertEqual(payload["symbol"], "000001.SZ")

    def test_get_live_stock_overview_profile_skips_detail_and_pankou_fetches(self) -> None:
        live_quote = {
            "symbol": "000001.SZ",
            "name": "平安银行",
            "sector": "货币金融服务",
            "current": 10.91,
            "change": -0.02,
            "percent": -0.18,
        }
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._fallback_stock_profile",
            return_value={"symbol": "000001.SZ", "name": "000001.SZ", "market": "A", "sector": "Unknown"},
        ), patch("app.services.live_market_service.get_cached_stock_basic", return_value=[]), patch(
            "app.services.live_market_service.get_stock_quote", return_value=live_quote
        ), patch("app.services.live_market_service.get_stock_quote_detail") as quote_detail, patch(
            "app.services.live_market_service.get_stock_pankou"
        ) as pankou, patch("app.services.live_market_service.set_json"):
            payload = get_live_stock_overview_profile("000001.SZ")

        quote_detail.assert_not_called()
        pankou.assert_not_called()
        self.assertIsNotNone(payload)
        self.assertNotIn("quote_detail", payload)
        self.assertNotIn("pankou", payload)

    def test_get_live_stock_profile_extras_uses_cached_extras_when_remote_missing(self) -> None:
        cached = {
            "symbol": "000001.SZ",
            "quote_detail": {"pe_ttm": 8.1},
            "pankou": {"diff": 100.0, "ratio": 0.12, "bids": [], "asks": []},
        }
        with patch("app.services.live_market_service.get_json", return_value=cached), patch(
            "app.services.live_market_service.get_stock_quote_detail", return_value={}
        ), patch("app.services.live_market_service.get_stock_pankou", return_value={}), patch(
            "app.services.live_market_service.set_json"
        ):
            payload = get_live_stock_profile_extras("000001.SZ")

        self.assertEqual(payload["quote_detail"]["pe_ttm"], 8.1)
        self.assertEqual(payload["pankou"]["diff"], 100.0)


if __name__ == "__main__":
    unittest.main()
