from __future__ import annotations

from datetime import date
from datetime import datetime
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
    get_live_stock_research,
)


class LiveMarketFallbackTests(unittest.TestCase):
    def test_identity_signal_requires_name_and_sector(self) -> None:
        self.assertFalse(_has_identity_signal({"symbol": "000001.SZ", "name": "000001.SZ", "sector": "Unknown"}))
        self.assertFalse(_has_identity_signal({"symbol": "000001.SZ", "name": "PingAn", "sector": "Unknown"}))
        self.assertTrue(_has_identity_signal({"symbol": "000001.SZ", "name": "PingAn", "sector": "Financials"}))

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
            payload = get_live_stock_profile("00700.HK", prefer_live=True)

        self.assertIsNotNone(payload)
        self.assertEqual(payload["quote"]["current"], 528.0)
        self.assertEqual(payload["quote"]["last_close"], 512.0)
        self.assertEqual(payload["name"], "Tencent")

    def test_get_live_stock_profile_can_fill_name_and_sector_from_quote(self) -> None:
        live_quote = {
            "symbol": "000001.SZ",
            "name": "PingAn",
            "sector": "Financials",
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
            payload = get_live_stock_profile("000001.SZ", prefer_live=True)

        self.assertIsNotNone(payload)
        self.assertEqual(payload["name"], "PingAn")
        self.assertEqual(payload["sector"], "Financials")
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

    def test_get_live_kline_uses_remote_when_local_day_series_only_has_one_point(self) -> None:
        db_rows = [
            {
                "symbol": "00700.HK",
                "date": date(2026, 3, 14),
                "open": 318.0,
                "high": 321.0,
                "low": 317.5,
                "close": 320.0,
                "volume": 1000.0,
            }
        ]
        remote_rows = [
            {
                "symbol": "00700.HK",
                "date": date(2026, 3, 14),
                "open": 318.0,
                "high": 321.0,
                "low": 317.5,
                "close": 320.0,
                "volume": 1000.0,
            },
            {
                "symbol": "00700.HK",
                "date": date(2026, 3, 17),
                "open": 320.0,
                "high": 323.0,
                "low": 319.8,
                "close": 322.5,
                "volume": 1200.0,
            },
        ]
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._load_db_daily_rows",
            return_value=db_rows,
        ), patch(
            "app.services.live_market_service.get_kline_history",
            return_value=remote_rows,
        ) as remote_kline, patch("app.services.live_market_service.set_json"):
            items = get_live_kline("00700.HK", period="day", limit=60)

        remote_kline.assert_called_once()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[-1].close, 322.5)

    def test_get_live_kline_prefers_local_intraday_rows_for_1m_series(self) -> None:
        db_rows = [
            {
                "symbol": "000001.SZ",
                "date": datetime(2026, 3, 16, 9, 31),
                "open": 10.0,
                "high": 10.1,
                "low": 9.9,
                "close": 10.05,
                "volume": 1000.0,
            },
            {
                "symbol": "000001.SZ",
                "date": datetime(2026, 3, 16, 9, 32),
                "open": 10.05,
                "high": 10.2,
                "low": 10.0,
                "close": 10.18,
                "volume": 1200.0,
            },
        ]
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._load_db_intraday_rows",
            return_value=db_rows,
        ), patch("app.services.live_market_service.get_kline_history") as remote_kline, patch(
            "app.services.live_market_service.set_json"
        ):
            items = get_live_kline("000001.SZ", period="1m", limit=60)

        remote_kline.assert_not_called()
        self.assertEqual(len(items), 2)
        self.assertEqual(items[-1].close, 10.18)

    def test_get_live_kline_uses_remote_months_when_local_year_series_only_has_one_point(self) -> None:
        cached = [
            {
                "date": date(2026, 3, 17),
                "open": 320.0,
                "high": 323.0,
                "low": 319.8,
                "close": 322.5,
            }
        ]
        db_rows = [
            {
                "symbol": "00700.HK",
                "date": date(2026, 3, 17),
                "open": 320.0,
                "high": 323.0,
                "low": 319.8,
                "close": 322.5,
                "volume": 1200.0,
            }
        ]
        remote_month_rows = [
            {
                "symbol": "00700.HK",
                "date": date(2025, 1, 31),
                "open": 280.0,
                "high": 300.0,
                "low": 270.0,
                "close": 295.0,
                "volume": 1000.0,
            },
            {
                "symbol": "00700.HK",
                "date": date(2025, 12, 31),
                "open": 300.0,
                "high": 340.0,
                "low": 290.0,
                "close": 330.0,
                "volume": 1000.0,
            },
            {
                "symbol": "00700.HK",
                "date": date(2026, 3, 31),
                "open": 320.0,
                "high": 350.0,
                "low": 310.0,
                "close": 345.0,
                "volume": 1000.0,
            },
        ]
        with patch("app.services.live_market_service.get_json", return_value=cached), patch(
            "app.services.live_market_service._load_db_daily_rows",
            return_value=db_rows,
        ), patch(
            "app.services.live_market_service.get_kline_history",
            return_value=remote_month_rows,
        ) as remote_kline, patch("app.services.live_market_service.set_json"):
            items = get_live_kline("00700.HK", period="year", limit=10)

        remote_kline.assert_called_once_with("00700.HK", period="month", count=132, as_of=None, is_index=False)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].date, date(2025, 12, 31))
        self.assertEqual(items[-1].close, 345.0)

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

    def test_get_live_stock_overview_profile_local_only_and_queue_background_refresh(self) -> None:
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._load_db_stock_live_snapshot", return_value={}
        ), patch(
            "app.services.live_market_service._fallback_stock_profile",
            return_value={"symbol": "000001.SZ", "name": "000001.SZ", "market": "A", "sector": "Unknown"},
        ), patch(
            "app.services.live_market_service.get_cached_stock_basic", return_value=[]
        ), patch("app.services.live_market_service._queue_background_profile_refresh") as queue_refresh, patch(
            "app.services.live_market_service.get_stock_quote"
        ) as quote, patch("app.services.live_market_service.get_stock_quote_detail") as quote_detail, patch(
            "app.services.live_market_service.get_stock_pankou"
        ) as pankou, patch("app.services.live_market_service.set_json"):
            payload = get_live_stock_overview_profile("000001.SZ", prefer_live=False)

        queue_refresh.assert_called_once_with("000001.SZ")
        quote.assert_not_called()
        quote_detail.assert_not_called()
        pankou.assert_not_called()
        self.assertIsNotNone(payload)
        self.assertNotIn("quote", payload)
        self.assertNotIn("quote_detail", payload)
        self.assertNotIn("pankou", payload)

    def test_get_live_stock_overview_profile_prefer_live_skips_detail_and_pankou_fetches(self) -> None:
        live_quote = {
            "symbol": "000001.SZ",
            "name": "PingAn",
            "sector": "Financials",
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
            payload = get_live_stock_overview_profile("000001.SZ", prefer_live=True)

        quote_detail.assert_not_called()
        pankou.assert_not_called()
        self.assertIsNotNone(payload)
        self.assertNotIn("quote_detail", payload)
        self.assertNotIn("pankou", payload)

    def test_get_live_stock_profile_extras_uses_cached_extras_without_remote_calls(self) -> None:
        cached = {
            "symbol": "000001.SZ",
            "quote_detail": {"pe_ttm": 8.1},
            "pankou": {"diff": 100.0, "ratio": 0.12, "bids": [], "asks": []},
        }
        with patch("app.services.live_market_service.get_json", return_value=cached), patch(
            "app.services.live_market_service._load_db_stock_live_snapshot", return_value={}
        ), patch("app.services.live_market_service._queue_background_profile_refresh") as queue_refresh, patch(
            "app.services.live_market_service.get_stock_quote_detail"
        ) as quote_detail, patch("app.services.live_market_service.get_stock_pankou") as pankou, patch(
            "app.services.live_market_service.set_json"
        ):
            payload = get_live_stock_profile_extras("000001.SZ", prefer_live=False)

        queue_refresh.assert_called_once_with("000001.SZ")
        quote_detail.assert_not_called()
        pankou.assert_not_called()
        self.assertEqual(payload["quote_detail"]["pe_ttm"], 8.1)
        self.assertEqual(payload["pankou"]["diff"], 100.0)

    def test_get_live_stock_profile_extras_prefers_local_snapshot(self) -> None:
        local_snapshot = {
            "symbol": "000001.SZ",
            "quote_detail": {"pe_ttm": 7.9},
            "pankou": {"diff": 88.0, "ratio": 0.09, "bids": [], "asks": []},
        }
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._load_db_stock_live_snapshot", return_value=local_snapshot
        ), patch("app.services.live_market_service._queue_background_profile_refresh") as queue_refresh, patch(
            "app.services.live_market_service.get_stock_quote_detail"
        ) as quote_detail, patch("app.services.live_market_service.get_stock_pankou") as pankou:
            payload = get_live_stock_profile_extras("000001.SZ", prefer_live=False)

        queue_refresh.assert_called_once_with("000001.SZ")
        quote_detail.assert_not_called()
        pankou.assert_not_called()
        self.assertEqual(payload["quote_detail"]["pe_ttm"], 7.9)
        self.assertEqual(payload["pankou"]["diff"], 88.0)

    def test_get_live_stock_profile_extras_prefer_live_fetches_remote_extras(self) -> None:
        remote_quote_detail = {"symbol": "000001.SZ", "pe_ttm": 9.3}
        remote_pankou = {"diff": 123.0, "ratio": 0.11, "bids": [], "asks": []}
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service.get_stock_quote_detail", return_value=remote_quote_detail
        ) as quote_detail, patch(
            "app.services.live_market_service.get_stock_pankou", return_value=remote_pankou
        ) as pankou, patch("app.services.live_market_service._queue_background_profile_refresh") as queue_refresh:
            payload = get_live_stock_profile_extras("000001.SZ", prefer_live=True)

        queue_refresh.assert_not_called()
        quote_detail.assert_called_once()
        pankou.assert_called_once()
        self.assertEqual(payload["quote_detail"]["pe_ttm"], 9.3)
        self.assertEqual(payload["pankou"]["diff"], 123.0)

    def test_get_live_stock_research_prefers_local_rows(self) -> None:
        local_reports = [
            {
                "title": "Local report",
                "published_at": None,
                "link": "",
                "summary": "",
                "institution": "",
                "rating": "",
                "source": "local",
            }
        ]
        local_forecasts = [
            {
                "title": "Local forecast",
                "published_at": None,
                "link": "",
                "summary": "",
                "institution": "",
                "rating": "",
                "source": "local",
            }
        ]
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._load_db_stock_research",
            side_effect=[local_reports, local_forecasts],
        ), patch("app.services.live_market_service.get_stock_reports") as reports, patch(
            "app.services.live_market_service.get_stock_earning_forecasts"
        ) as forecasts, patch("app.services.live_market_service.set_json"):
            payload = get_live_stock_research("000001.SZ")

        reports.assert_not_called()
        forecasts.assert_not_called()
        self.assertEqual(payload["reports"][0]["title"], "Local report")
        self.assertEqual(payload["earning_forecasts"][0]["title"], "Local forecast")


if __name__ == "__main__":
    unittest.main()
