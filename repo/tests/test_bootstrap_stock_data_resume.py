from __future__ import annotations

from contextlib import nullcontext
from datetime import date
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import etl.bootstrap_stock_data as bootstrap_stock_data


class BootstrapStockDataResumeTests(unittest.TestCase):
    def test_run_bootstrap_resumes_from_checkpoint(self) -> None:
        as_of = date(2026, 3, 16)
        stock_rows = [
            {"symbol": "000001.SZ", "name": "Ping An Bank", "market": "A", "sector": "Bank"},
            {"symbol": "00700.HK", "name": "Tencent", "market": "HK", "sector": "Tech"},
            {"symbol": "00005.HK", "name": "HSBC", "market": "HK", "sector": "Bank"},
        ]
        state_dir = ROOT / "state" / "test_bootstrap_stock_data_resume"
        checkpoint_path = state_dir / "bootstrap_stock_data_checkpoint.json"
        if state_dir.exists():
            shutil.rmtree(state_dir, ignore_errors=True)
        state_dir.mkdir(parents=True, exist_ok=True)

        daily_calls_first: list[str] = []
        daily_calls_second: list[str] = []
        try:
            with patch.object(bootstrap_stock_data, "STATE_DIR", state_dir), patch.object(
                bootstrap_stock_data, "CHECKPOINT_PATH", checkpoint_path
            ), patch.object(
                bootstrap_stock_data,
                "get_market_stock_pool",
                side_effect=[
                    [{"symbol": "000001.SZ"}],
                    [{"symbol": "00700.HK"}, {"symbol": "00005.HK"}],
                ],
            ), patch.object(
                bootstrap_stock_data, "market_data_session", return_value=nullcontext()
            ), patch.object(
                bootstrap_stock_data, "get_stock_basic", return_value=stock_rows
            ), patch.object(
                bootstrap_stock_data, "upsert_stocks", side_effect=lambda rows: len(list(rows))
            ), patch.object(
                bootstrap_stock_data, "get_index_history", return_value=[{"symbol": "000001.SH", "date": as_of}]
            ), patch.object(
                bootstrap_stock_data, "upsert_daily_prices", side_effect=lambda rows: len(list(rows))
            ), patch.object(
                bootstrap_stock_data, "upsert_financials", side_effect=lambda rows: len(list(rows))
            ), patch.object(
                bootstrap_stock_data, "_upsert_latest_fundamental", return_value=1
            ), patch.object(
                bootstrap_stock_data,
                "get_financials",
                side_effect=lambda symbol, period: {
                    "symbol": symbol,
                    "period": period,
                    "revenue": 1,
                    "net_income": 1,
                    "cash_flow": 1,
                    "debt_ratio": 1,
                },
            ):

                def interrupting_daily_history(symbol: str, *, count: int, as_of: date | None = None) -> list[dict]:
                    daily_calls_first.append(symbol)
                    if symbol == "00005.HK":
                        raise KeyboardInterrupt("stop after committed symbols")
                    return [{"symbol": symbol, "date": as_of}]

                with patch.object(bootstrap_stock_data, "get_daily_history", side_effect=interrupting_daily_history):
                    with self.assertRaises(KeyboardInterrupt):
                        bootstrap_stock_data.run_bootstrap(
                            as_of=as_of,
                            daily_count=5,
                            financial_periods=2,
                            a_count=1,
                            hk_count=2,
                        )

            self.assertTrue(checkpoint_path.exists())
            self.assertEqual(daily_calls_first, ["000001.SZ", "00700.HK", "00005.HK"])
            with patch.object(bootstrap_stock_data, "CHECKPOINT_PATH", checkpoint_path):
                checkpoint = bootstrap_stock_data._load_checkpoint(
                    bootstrap_stock_data._checkpoint_signature(
                        target_date=as_of,
                        daily_count=5,
                        financial_periods=2,
                        a_count=1,
                        hk_count=2,
                    )
                )
            self.assertIsNotNone(checkpoint)
            self.assertEqual(checkpoint["next_symbol_index"], 2)
            self.assertTrue(checkpoint["index_done"])

            with patch.object(bootstrap_stock_data, "STATE_DIR", state_dir), patch.object(
                bootstrap_stock_data, "CHECKPOINT_PATH", checkpoint_path
            ), patch.object(
                bootstrap_stock_data, "get_market_stock_pool", side_effect=AssertionError("should use checkpoint symbols")
            ), patch.object(
                bootstrap_stock_data, "market_data_session", return_value=nullcontext()
            ), patch.object(
                bootstrap_stock_data, "get_stock_basic", return_value=stock_rows
            ), patch.object(
                bootstrap_stock_data, "upsert_stocks", side_effect=lambda rows: len(list(rows))
            ), patch.object(
                bootstrap_stock_data, "get_index_history"
            ) as index_mock, patch.object(
                bootstrap_stock_data, "upsert_daily_prices", side_effect=lambda rows: len(list(rows))
            ), patch.object(
                bootstrap_stock_data, "upsert_financials", side_effect=lambda rows: len(list(rows))
            ), patch.object(
                bootstrap_stock_data, "_upsert_latest_fundamental", return_value=1
            ), patch.object(
                bootstrap_stock_data,
                "get_financials",
                side_effect=lambda symbol, period: {
                    "symbol": symbol,
                    "period": period,
                    "revenue": 1,
                    "net_income": 1,
                    "cash_flow": 1,
                    "debt_ratio": 1,
                },
            ):

                def resumed_daily_history(symbol: str, *, count: int, as_of: date | None = None) -> list[dict]:
                    daily_calls_second.append(symbol)
                    return [{"symbol": symbol, "date": as_of}]

                with patch.object(bootstrap_stock_data, "get_daily_history", side_effect=resumed_daily_history):
                    counters = bootstrap_stock_data.run_bootstrap(
                        as_of=as_of,
                        daily_count=5,
                        financial_periods=2,
                        a_count=1,
                        hk_count=2,
                    )

            index_mock.assert_not_called()
            self.assertEqual(daily_calls_second, ["00005.HK"])
            self.assertEqual(counters["daily_prices"], 1)
            self.assertEqual(counters["financials"], 2)
            self.assertFalse(checkpoint_path.exists())
        finally:
            if state_dir.exists():
                shutil.rmtree(state_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
