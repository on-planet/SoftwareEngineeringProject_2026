from __future__ import annotations

from datetime import date
from pathlib import Path
import os
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from etl.fetchers import events_client, news_client, snowball_client


class HongKongEtlFallbackTests(unittest.TestCase):
    def test_external_market_feeds_include_quanwenrss_sources(self) -> None:
        feeds = news_client._external_market_feeds()
        self.assertIn("https://quanwenrss.com/caixin/economy", feeds)
        self.assertIn("https://quanwenrss.com/politico/finance", feeds)

    def test_event_symbols_expand_with_cached_hk_universe(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(events_client, "list_cached_symbols", return_value=["00700.HK", "00005.HK"]),
        ):
            self.assertEqual(
                events_client._event_symbols(),
                ["600000.SH", "000001.SZ", "600519.SH", "00700.HK", "00005.HK"],
            )

    def test_buyback_uses_hkex_official_feed(self) -> None:
        self.assertIn("hkex.com.hk", events_client._hkex_regulatory_announcements_rss())

    def test_zero_only_financial_rows_are_treated_as_invalid(self) -> None:
        self.assertFalse(
            snowball_client._financial_row_has_signal(
                {
                    "revenue": 0.0,
                    "net_income": 0.0,
                    "cash_flow": 0.0,
                    "roe": 0.0,
                    "debt_ratio": 0.0,
                }
            )
        )
        self.assertTrue(
            snowball_client._financial_row_has_signal(
                {
                    "revenue": 0.0,
                    "net_income": 1.0,
                    "cash_flow": 0.0,
                    "roe": 0.0,
                    "debt_ratio": 0.0,
                }
            )
        )

    def test_hk_quote_prefers_snowball_over_akshare_spot(self) -> None:
        snowball_quote = [
            {
                "symbol": "00700.HK",
                "name": "Tencent",
                "current": 320.5,
                "change": 1.2,
                "percent": 0.38,
                "open": 319.0,
                "high": 321.0,
                "low": 318.4,
                "last_close": 319.3,
                "volume": 123456,
                "amount": 3456789,
            }
        ]
        with patch.object(
            snowball_client,
            "_call_quotec",
            return_value=snowball_quote,
        ) as quotec_mock, patch.object(
            snowball_client,
            "_get_ak_hk_spot_quote",
        ) as ak_hk_quote_mock:
            quote = snowball_client.get_stock_quote("00700.HK")

        quotec_mock.assert_called_once()
        ak_hk_quote_mock.assert_not_called()
        self.assertEqual(quote["symbol"], "00700.HK")
        self.assertEqual(quote["name"], "Tencent")
        self.assertEqual(quote["current"], 320.5)
        self.assertEqual(quote["change"], 1.2)

    def test_hk_quote_falls_back_to_akshare_spot_when_snowball_empty(self) -> None:
        hk_quote = {
            "symbol": "00700.HK",
            "name": "Tencent",
            "current": 320.5,
            "change": 1.2,
            "percent": 0.38,
        }
        with patch.object(
            snowball_client,
            "_call_quotec",
            return_value=[],
        ), patch.object(
            snowball_client,
            "_call_quotec_single",
            return_value=None,
        ), patch.object(
            snowball_client,
            "_get_ak_hk_spot_quote",
            return_value=hk_quote,
        ) as ak_hk_quote_mock:
            quote = snowball_client.get_stock_quote("00700.HK")

        ak_hk_quote_mock.assert_called_once_with("00700.HK", allow_refresh=False)
        self.assertEqual(quote["symbol"], "00700.HK")
        self.assertEqual(quote["name"], "Tencent")

    def test_a_share_reports_prefer_akshare_szse_margin_underlying(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "\u8bc1\u5238\u4ee3\u7801": "000001",
                    "\u8bc1\u5238\u7b80\u79f0": "PingAnBank",
                    "\u878d\u8d44\u4e70\u5165\u6807\u7684": "\u662f",
                    "\u878d\u5238\u5356\u51fa\u6807\u7684": "\u662f",
                    "\u878d\u8d44\u4fdd\u8bc1\u91d1\u6bd4\u4f8b": "100%",
                }
            ]
        )
        snowball_client._AK_A_MARGIN_CACHE_TS = 0.0
        snowball_client._AK_A_MARGIN_CACHE_DATE = ""
        snowball_client._AK_A_MARGIN_CACHE_ROWS = []
        snowball_client._AK_A_MARGIN_CACHE_READY = False
        with patch.object(
            snowball_client,
            "ak",
            SimpleNamespace(stock_margin_underlying_info_szse=lambda date: frame),
        ), patch.object(
            snowball_client,
            "_call_with_token_retry",
        ) as snowball_call:
            rows = snowball_client.get_stock_reports("000001.SZ", limit=5)

        snowball_call.assert_not_called()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "AkShare SZSE Margin Underlying")
        self.assertIn("SZSE margin underlying", rows[0]["title"])

    def test_hk_reports_prefer_akshare_profit_forecast(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "\u673a\u6784": "BrokerA",
                    "\u6700\u65b0\u8bc4\u7ea7": "Buy",
                    "\u53d1\u5e03\u65e5\u671f": "2026-03-15",
                    "2026E": "5.2",
                },
                {
                    "\u673a\u6784": "BrokerB",
                    "\u6700\u65b0\u8bc4\u7ea7": "Hold",
                    "\u53d1\u5e03\u65e5\u671f": "2026-03-16",
                    "2026E": "4.8",
                },
            ]
        )
        with patch.object(
            snowball_client,
            "ak",
            SimpleNamespace(stock_hk_profit_forecast_et=lambda symbol, indicator: frame),
        ), patch.object(
            snowball_client,
            "_call_with_token_retry",
        ) as snowball_call:
            rows = snowball_client.get_stock_reports("09999.HK", limit=1)
            forecasts = snowball_client.get_stock_earning_forecasts("09999.HK", limit=1)

        snowball_call.assert_not_called()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "AkShare HK Profit Forecast")
        self.assertIn("BrokerB", rows[0]["title"])
        self.assertEqual(len(forecasts), 1)
        self.assertEqual(forecasts[0]["source"], "AkShare HK Profit Forecast")

    def test_hk_reports_fallback_to_snowball_when_akshare_no_data_index_error(self) -> None:
        def bad_fetch(symbol, indicator):
            raise IndexError("list index out of range")

        fallback_rows = [
            {
                "title": "Snowball HK report",
                "published_at": None,
                "link": "",
                "summary": "",
                "institution": "",
                "rating": "",
                "source": "雪球研报",
            }
        ]
        with patch.object(
            snowball_client,
            "ak",
            SimpleNamespace(stock_hk_profit_forecast_et=bad_fetch),
        ), patch.object(
            snowball_client,
            "_call_with_token_retry",
            return_value={"ok": True},
        ) as snowball_call, patch.object(
            snowball_client,
            "_extract_disclosure_items",
            return_value=fallback_rows,
        ):
            rows = snowball_client.get_stock_reports("00113.HK", limit=1)

        snowball_call.assert_called()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "雪球研报")

    def test_hk_kline_uses_akshare_when_snowball_unavailable(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "\u65e5\u671f": "2026-03-14",
                    "\u5f00\u76d8": 318.0,
                    "\u6536\u76d8": 320.0,
                    "\u6700\u9ad8": 321.0,
                    "\u6700\u4f4e": 317.5,
                    "\u6210\u4ea4\u91cf": 100000,
                },
                {
                    "\u65e5\u671f": "2026-03-17",
                    "\u5f00\u76d8": 320.0,
                    "\u6536\u76d8": 322.5,
                    "\u6700\u9ad8": 323.0,
                    "\u6700\u4f4e": 319.8,
                    "\u6210\u4ea4\u91cf": 120000,
                },
            ]
        )
        with patch.object(
            snowball_client,
            "ball",
            None,
        ), patch.object(
            snowball_client,
            "ak",
            SimpleNamespace(stock_hk_hist=lambda **kwargs: frame),
        ), patch.object(
            snowball_client,
            "_call_kline_with_retry",
        ) as snowball_kline:
            rows = snowball_client.get_kline_history("00700.HK", period="day", count=60, as_of=None, is_index=False)

        snowball_kline.assert_not_called()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["symbol"], "00700.HK")
        self.assertEqual(rows[-1]["close"], 322.5)

    def test_hk_kline_prefers_snowball_when_it_has_multiple_rows(self) -> None:
        payload = {
            "data": {
                "column": ["timestamp", "open", "close", "high", "low", "volume"],
                "item": [
                    ["2026-03-14", 318, 320, 321, 317.5, 100000],
                    ["2026-03-17", 320, 322.5, 323, 319.8, 120000],
                ],
            }
        }

        class FakeBall:
            @staticmethod
            def kline(symbol: str, period: str, count: int):
                return payload

        with patch.object(
            snowball_client,
            "ball",
            FakeBall(),
        ), patch.object(
            snowball_client,
            "_ensure_token",
            return_value=True,
        ), patch.object(
            snowball_client,
            "_fetch_ak_hk_kline_history",
        ) as ak_fallback:
            rows = snowball_client.get_kline_history("00700.HK", period="day", count=60, as_of=None, is_index=False)

        ak_fallback.assert_not_called()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]["close"], 322.5)

    def test_hk_kline_falls_back_to_akshare_when_snowball_only_has_one_row(self) -> None:
        payload = {
            "data": {
                "column": ["timestamp", "open", "close", "high", "low", "volume"],
                "item": [
                    ["2026-03-17", 320, 322.5, 323, 319.8, 120000],
                ],
            }
        }

        class FakeBall:
            @staticmethod
            def kline(symbol: str, period: str, count: int):
                return payload

        ak_rows = [
            {
                "symbol": "00700.HK",
                "date": date(2026, 3, 14),
                "open": 318.0,
                "high": 321.0,
                "low": 317.5,
                "close": 320.0,
                "volume": 100000.0,
            },
            {
                "symbol": "00700.HK",
                "date": date(2026, 3, 17),
                "open": 320.0,
                "high": 323.0,
                "low": 319.8,
                "close": 322.5,
                "volume": 120000.0,
            },
        ]
        with patch.object(
            snowball_client,
            "ball",
            FakeBall(),
        ), patch.object(
            snowball_client,
            "_ensure_token",
            return_value=True,
        ), patch.object(
            snowball_client,
            "_fetch_ak_hk_kline_history",
            return_value=ak_rows,
        ):
            rows = snowball_client.get_kline_history("00700.HK", period="day", count=60, as_of=None, is_index=False)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["date"], date(2026, 3, 14))
        self.assertEqual(rows[-1]["close"], 322.5)

    def test_hk_kline_uses_curl_eastmoney_fallback_when_python_network_is_blocked(self) -> None:
        payload = {
            "data": {
                "column": ["timestamp", "open", "close", "high", "low", "volume"],
                "item": [],
            }
        }

        class FakeBall:
            @staticmethod
            def kline(symbol: str, period: str, count: int):
                return payload

        curl_json = (
            '{"data":{"klines":['
            '"2026-03-14,318,320,321,317.5,100000",'
            '"2026-03-17,320,322.5,323,319.8,120000"'
            "]}}"
        )

        with patch.object(
            snowball_client,
            "ball",
            FakeBall(),
        ), patch.object(
            snowball_client,
            "_ensure_token",
            return_value=True,
        ), patch.object(
            snowball_client,
            "ak",
            SimpleNamespace(stock_hk_hist=lambda **kwargs: (_ for _ in ()).throw(OSError("WinError 10013"))),
        ), patch.object(
            snowball_client.shutil,
            "which",
            return_value="C:\\Windows\\System32\\curl.exe",
        ), patch.object(
            snowball_client.subprocess,
            "run",
            return_value=SimpleNamespace(returncode=0, stdout=curl_json, stderr=""),
        ):
            rows = snowball_client.get_kline_history("00700.HK", period="day", count=60, as_of=None, is_index=False)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["date"], date(2026, 3, 14))
        self.assertEqual(rows[-1]["close"], 322.5)

    def test_a_share_reports_compat_path_handles_bytes_read_excel_error(self) -> None:
        class FakeResponse:
            content = b"xlsx"

            @staticmethod
            def raise_for_status():
                return None

        class FakeFrame:
            @staticmethod
            def to_dict(orient: str = "records"):
                assert orient == "records"
                return [{"code": "000001", "name": "PingAnBank"}]

        def bad_fetch(date: str):
            raise TypeError("Expected file path name or file-like object, got <class 'bytes'> type")

        snowball_client._AK_A_MARGIN_CACHE_TS = 0.0
        snowball_client._AK_A_MARGIN_CACHE_DATE = ""
        snowball_client._AK_A_MARGIN_CACHE_ROWS = []
        snowball_client._AK_A_MARGIN_CACHE_READY = False
        with patch.object(
            snowball_client,
            "ak",
            SimpleNamespace(stock_margin_underlying_info_szse=bad_fetch),
        ), patch.object(
            snowball_client,
            "requests",
            SimpleNamespace(get=lambda *args, **kwargs: FakeResponse()),
        ), patch.object(
            snowball_client,
            "pd",
            SimpleNamespace(read_excel=lambda *args, **kwargs: FakeFrame()),
        ), patch.object(
            snowball_client,
            "_call_with_token_retry",
        ) as snowball_call:
            rows = snowball_client.get_stock_reports("000001.SZ", limit=5)

        snowball_call.assert_not_called()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "AkShare SZSE Margin Underlying")


if __name__ == "__main__":
    unittest.main()
