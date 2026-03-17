from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
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
        ):
            event_rows = events_client.get_events(date(2026, 3, 16))
            insider_rows = events_client.get_insider_trade(date(2026, 3, 16))

        self.assertEqual(len(event_rows), 3)
        self.assertEqual({row["symbol"] for row in event_rows}, {"00700.HK", "00005.HK"})
        self.assertEqual(len(insider_rows), 2)
        self.assertEqual({row["symbol"] for row in insider_rows}, {"00700.HK", "00005.HK"})

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
