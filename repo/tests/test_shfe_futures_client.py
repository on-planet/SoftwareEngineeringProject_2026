from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from etl.fetchers import futures_client


class ShfeFuturesClientTests(unittest.TestCase):
    @patch("etl.fetchers.futures_client.ak")
    def test_get_futures_daily_returns_normalized_rows(self, mock_ak: Mock) -> None:
        mock_ak.futures_zh_daily_sina.return_value = pd.DataFrame({
            "date": ["2026-03-13", "2026-03-12", "2026-03-11"],
            "open": [101240.0, 101000.0, 100800.0],
            "high": [101250.0, 101100.0, 100900.0],
            "low": [100080.0, 100000.0, 99800.0],
            "close": [100310.0, 100200.0, 100100.0],
            "volume": [85149, 80000, 75000],
            "hold": [190911, 190000, 189000],
            "settle": [100600.0, 100500.0, 100400.0],
        })

        rows = futures_client.get_futures_daily(date(2026, 3, 13))

        cu_row = next((r for r in rows if r["symbol"] == "CU"), None)
        self.assertIsNotNone(cu_row)
        self.assertEqual(cu_row["date"], date(2026, 3, 13))
        self.assertEqual(cu_row["close"], 100310.0)
        self.assertEqual(cu_row["settlement"], 100600.0)
        self.assertEqual(cu_row["source"], "AkShare")
        self.assertIsNone(cu_row["contract_month"])

    @patch("etl.fetchers.futures_client.ak")
    def test_get_futures_daily_returns_empty_when_akshare_fails(self, mock_ak: Mock) -> None:
        mock_ak.futures_zh_daily_sina.side_effect = RuntimeError("network error")

        rows = futures_client.get_futures_daily(date(2026, 3, 13))

        self.assertEqual(rows, [])

    @patch("etl.fetchers.futures_client.ak")
    def test_get_futures_weekly_returns_same_format(self, mock_ak: Mock) -> None:
        mock_ak.futures_zh_daily_sina.return_value = pd.DataFrame({
            "date": ["2026-03-13", "2026-03-12"],
            "open": [101240.0, 101000.0],
            "high": [101250.0, 101100.0],
            "low": [100080.0, 100000.0],
            "close": [100310.0, 100200.0],
            "volume": [85149, 80000],
            "hold": [190911, 190000],
            "settle": [100600.0, 100500.0],
        })

        rows = futures_client.get_futures_weekly(date(2026, 3, 13))

        cu_row = next((r for r in rows if r["symbol"] == "CU"), None)
        self.assertIsNotNone(cu_row)
        self.assertEqual(cu_row["source"], "AkShare")

    def test_target_products_cover_expected_symbols(self) -> None:
        symbols = {v["symbol"] for v in futures_client.TARGET_PRODUCTS.values()}
        self.assertEqual(symbols, {"CU", "AU", "AG", "AO", "SC", "FU"})


if __name__ == "__main__":
    unittest.main()
