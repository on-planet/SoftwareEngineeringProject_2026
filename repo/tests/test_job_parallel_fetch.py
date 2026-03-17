from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import json
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

if "pydantic_settings" not in sys.modules:
    fake_module = types.ModuleType("pydantic_settings")

    class BaseSettings:  # pragma: no cover - import shim for tests
        def __init__(self, **kwargs):
            annotations: dict[str, object] = {}
            for cls in reversed(self.__class__.mro()):
                annotations.update(getattr(cls, "__annotations__", {}))
            for key in annotations:
                if key in kwargs:
                    value = kwargs[key]
                else:
                    value = getattr(self.__class__, key, None)
                setattr(self, key, value)

    fake_module.BaseSettings = BaseSettings
    sys.modules["pydantic_settings"] = fake_module

from etl.fetchers import events_client
from etl.jobs import financial_job
from etl.jobs import stock_detail_job


class JobParallelFetchTests(unittest.TestCase):
    def test_financial_job_collects_all_symbol_rows_with_parallel_workers(self) -> None:
        financial_rows_written: list[dict] = []
        score_rows_written: list[dict] = []

        def fake_get_financials(symbol: str, period: str) -> dict:
            return {
                "symbol": symbol,
                "period": period,
                "revenue": 100.0 if symbol == "000001.SZ" else 120.0,
                "net_income": 20.0,
                "cash_flow": 18.0,
                "roe": 0.12,
                "debt_ratio": 0.35,
            }

        with (
            patch.object(financial_job, "_iter_symbols", return_value=["000001.SZ", "600000.SH"]),
            patch.object(financial_job, "get_latest_financial_periods", return_value={}),
            patch.object(financial_job, "get_financials", side_effect=fake_get_financials),
            patch.object(financial_job, "generate_summary", return_value="summary"),
            patch.object(financial_job, "FINANCIAL_JOB_WORKERS", 2),
            patch.object(financial_job, "upsert_financials", side_effect=lambda rows: financial_rows_written.extend(rows) or len(rows)),
            patch.object(financial_job, "upsert_fundamental_score", side_effect=lambda rows: score_rows_written.extend(rows) or len(rows)),
        ):
            total = financial_job.run_financial_job(date(2026, 3, 16), date(2026, 3, 16))

        self.assertEqual(total, 2)
        self.assertEqual(len(financial_rows_written), 2)
        self.assertEqual({row["symbol"] for row in financial_rows_written}, {"000001.SZ", "600000.SH"})
        self.assertEqual(len(score_rows_written), 2)

    def test_events_client_collects_symbol_reports_and_insider_rows(self) -> None:
        class FakeBall:
            @staticmethod
            def report(symbol: str):
                return [
                    {
                        "title": f"report-{symbol}",
                        "date": "2026-03-16",
                        "url": f"https://example.com/{symbol}/report",
                    }
                ]

            @staticmethod
            def skholderchg(symbol: str):
                return [
                    {
                        "type": "buy",
                        "date": "2026-03-16",
                        "shares": 1000,
                        "url": f"https://example.com/{symbol}/insider",
                    }
                ]

        rss_items = [
            {
                "title": "股份代號：700 騰訊控股 公告",
                "link": "https://www.hkex.com.hk/News/1",
                "published_at": datetime(2026, 3, 16, 3, 0, tzinfo=timezone.utc),
            }
        ]

        with (
            patch.object(events_client, "ball", FakeBall()),
            patch.object(events_client, "_event_symbols", return_value=["00700.HK", "00005.HK"]),
            patch.object(events_client, "EVENTS_SYMBOL_WORKERS", 2),
            patch.object(events_client, "_fetch_rss", return_value=rss_items),
            patch.object(events_client, "_fetch_akshare_company_dynamic_events", return_value=[]),
        ):
            event_rows = events_client.get_events(date(2026, 3, 16))
            insider_rows = events_client.get_insider_trade(date(2026, 3, 16))

        self.assertEqual(len(event_rows), 3)
        self.assertEqual({row["symbol"] for row in event_rows}, {"00700.HK", "00005.HK"})
        self.assertEqual(len(insider_rows), 2)
        self.assertEqual({row["symbol"] for row in insider_rows}, {"00700.HK", "00005.HK"})

    def test_fetch_akshare_company_dynamic_events_maps_rows(self) -> None:
        as_of = date.today()

        class FakeFrame:
            def __init__(self, rows: list[dict]):
                self._rows = rows

            def to_dict(self, orient: str = "records"):
                assert orient == "records"
                return list(self._rows)

        class FakeAk:
            @staticmethod
            def stock_zh_a_new():
                return FakeFrame(
                    [
                        {
                            "code": "000001",
                            "name": "PingAnBank",
                            "title": "Strategic cooperation",
                            "date": as_of.isoformat(),
                            "link": "https://example.com/000001",
                        },
                        {
                            "code": "300750",
                            "name": "CATL",
                            "date": as_of.isoformat(),
                            "industry": "Battery",
                        },
                        {
                            "code": "600519",
                            "name": "KweichowMoutai",
                            "title": "Historical event",
                            "date": "2026-03-15",
                        },
                    ]
                )

        with patch.object(events_client, "ak", FakeAk()):
            rows = events_client._fetch_akshare_company_dynamic_events(as_of)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["symbol"], "000001.SZ")
        self.assertEqual(rows[0]["type"], "company_dynamic")
        self.assertEqual(rows[0]["source"], "AkShare stock_zh_a_new")
        self.assertEqual(rows[1]["symbol"], "300750.SZ")
        self.assertIn("CATL", rows[1]["title"])

    def test_fetch_akshare_company_dynamic_events_maps_stock_zh_a_new_quote_rows(self) -> None:
        as_of = date.today()

        class FakeFrame:
            def __init__(self, rows: list[dict]):
                self._rows = rows

            def to_dict(self, orient: str = "records"):
                assert orient == "records"
                return list(self._rows)

        class FakeAk:
            @staticmethod
            def stock_zh_a_new():
                return FakeFrame(
                    [
                        {
                            "code": "301000",
                            "name": "NewCo",
                            "open": "12.3",
                            "high": "13.2",
                            "low": "11.8",
                            "volume": "230000",
                        }
                    ]
                )

        with patch.object(events_client, "ak", FakeAk()):
            rows = events_client._fetch_akshare_company_dynamic_events(as_of)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "301000.SZ")
        self.assertEqual(rows[0]["date"], as_of)
        self.assertIn("company dynamic", rows[0]["title"])

    def test_fetch_akshare_company_dynamic_events_uses_curl_fallback_when_network_blocked(self) -> None:
        as_of = date.today()

        class FakeAk:
            @staticmethod
            def stock_zh_a_new():
                raise RuntimeError("WinError 10013 blocked")

        def fake_run(cmd, **kwargs):
            cmd_text = " ".join(cmd)
            if "40.push2.eastmoney.com" in cmd_text:
                payload = json.dumps(
                    {
                        "data": {
                            "diff": [
                                {
                                    "f12": "300001",
                                    "f14": "CurlCo",
                                    "f17": "21.5",
                                    "f15": "22.1",
                                    "f16": "20.9",
                                    "f5": "123",
                                    "f6": "456",
                                }
                            ]
                        }
                    }
                ).encode("utf-8")
                return types.SimpleNamespace(returncode=0, stdout=payload, stderr=b"")
            if "getHQNodeStockCount" in cmd_text:
                return types.SimpleNamespace(returncode=0, stdout=b"80", stderr=b"")
            payload = json.dumps([]).encode("utf-8")
            return types.SimpleNamespace(returncode=0, stdout=payload, stderr=b"")

        with (
            patch.object(events_client, "ak", FakeAk()),
            patch.object(events_client.shutil, "which", return_value="curl.exe"),
            patch.object(events_client.subprocess, "run", side_effect=fake_run),
        ):
            rows = events_client._fetch_akshare_company_dynamic_events(as_of)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "300001.SZ")
        self.assertEqual(rows[0]["source"], "AkShare stock_zh_a_new")

    def test_get_events_keeps_akshare_rows_when_snowball_is_unavailable(self) -> None:
        ak_rows = [
            {
                "symbol": "000001.SZ",
                "type": "company_dynamic",
                "title": "Company dynamic",
                "date": date(2026, 3, 16),
                "link": "",
                "source": "AkShare stock_zh_a_new",
            }
        ]
        with (
            patch.object(events_client, "ball", None),
            patch.object(events_client, "_get_hkex_regulatory_announcements", return_value=[]),
            patch.object(events_client, "_fetch_akshare_company_dynamic_events", return_value=ak_rows),
        ):
            rows = events_client.get_events(date(2026, 3, 16))
        self.assertEqual(rows, ak_rows)

    def test_stock_detail_collect_symbol_payload_keeps_partial_sections_when_one_fails(self) -> None:
        with (
            patch.object(stock_detail_job, "_snapshot_row", return_value={"symbol": "000001.SZ"}),
            patch.object(stock_detail_job, "_research_rows", side_effect=RuntimeError("research boom")),
            patch.object(stock_detail_job, "_intraday_rows", return_value=[{"symbol": "000001.SZ", "period": "1m", "timestamp": 1}]),
            patch.object(stock_detail_job, "SECTION_WORKERS", 3),
        ):
            payload = stock_detail_job._collect_symbol_payload("000001.SZ", report_limit=10, forecast_limit=10)

        self.assertEqual(payload["symbol"], "000001.SZ")
        self.assertEqual(payload["snapshot"], {"symbol": "000001.SZ"})
        self.assertEqual(payload["research"], [])
        self.assertEqual(payload["intraday"], [{"symbol": "000001.SZ", "period": "1m", "timestamp": 1}])

    def test_snapshot_row_keeps_detail_and_pankou_when_quote_fails(self) -> None:
        with (
            patch.object(stock_detail_job, "get_stock_quote", side_effect=RuntimeError("quote boom")),
            patch.object(stock_detail_job, "get_stock_quote_detail", return_value={"pe_ttm": 12.3, "market_cap": 100.0}),
            patch.object(stock_detail_job, "get_stock_pankou", return_value={"diff": 1000, "ratio": 0.12, "bids": [], "asks": []}),
            patch.object(stock_detail_job, "SNAPSHOT_WORKERS", 3),
        ):
            row = stock_detail_job._snapshot_row("000001.SZ")

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["symbol"], "000001.SZ")
        self.assertIsNone(row["current"])
        self.assertEqual(row["pe_ttm"], 12.3)
        self.assertEqual(row["market_cap"], 100.0)
        self.assertEqual(row["pankou_diff"], 1000)
        self.assertEqual(row["pankou_ratio"], 0.12)

    def test_research_rows_keeps_reports_when_forecasts_fail(self) -> None:
        with (
            patch.object(
                stock_detail_job,
                "get_stock_reports",
                return_value=[{"title": "研报A", "published_at": None, "link": "r", "summary": "s", "institution": "i", "rating": "buy", "source": "snowball"}],
            ),
            patch.object(stock_detail_job, "get_stock_earning_forecasts", side_effect=RuntimeError("forecast boom")),
            patch.object(stock_detail_job, "RESEARCH_WORKERS", 2),
        ):
            rows = stock_detail_job._research_rows("000001.SZ", report_limit=10, forecast_limit=10)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "000001.SZ")
        self.assertEqual(rows[0]["item_type"], "report")
        self.assertEqual(rows[0]["title"], "研报A")


if __name__ == "__main__":
    unittest.main()
