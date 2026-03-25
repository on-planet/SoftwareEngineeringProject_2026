from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from app.schemas.kline import KlineCompareIn, KlineCompareSeriesIn
from app.services.kline_service import get_compare_kline


class KlineCompareBatchTests(unittest.TestCase):
    def test_get_compare_kline_preserves_request_order(self) -> None:
        payload = KlineCompareIn(
            period="day",
            limit=120,
            series=[
                KlineCompareSeriesIn(symbol="000001.SH", kind="index"),
                KlineCompareSeriesIn(symbol="000001.SZ", kind="stock", start=date(2026, 3, 1)),
                KlineCompareSeriesIn(symbol="00700.HK", kind="stock", start=date(2026, 3, 5)),
            ],
        )

        with patch(
            "app.services.kline_service.get_index_kline",
            return_value=[{"date": "2026-03-24", "open": 1, "high": 2, "low": 1, "close": 2}],
        ) as get_index_kline, patch(
            "app.services.kline_service.get_stock_kline",
            side_effect=[
                [{"date": "2026-03-24", "open": 10, "high": 11, "low": 9, "close": 10.5}],
                [{"date": "2026-03-24", "open": 20, "high": 21, "low": 19, "close": 20.5}],
            ],
        ) as get_stock_kline:
            result = get_compare_kline(payload)

        self.assertEqual(result["period"], "day")
        self.assertEqual(result["limit"], 120)
        self.assertEqual(
            [item["symbol"] for item in result["series"]],
            ["000001.SH", "000001.SZ", "00700.HK"],
        )
        self.assertTrue(all(item["error"] is None for item in result["series"]))
        get_index_kline.assert_called_once_with("000001.SH", period="day", limit=120, end=None, start=None)
        self.assertEqual(get_stock_kline.call_count, 2)

    def test_get_compare_kline_returns_per_series_errors_without_failing_batch(self) -> None:
        payload = KlineCompareIn(
            period="day",
            limit=60,
            series=[
                KlineCompareSeriesIn(symbol="000001.SH", kind="index"),
                KlineCompareSeriesIn(symbol="BAD.SYMBOL", kind="stock"),
            ],
        )

        with patch(
            "app.services.kline_service.get_index_kline",
            return_value=[{"date": "2026-03-24", "open": 1, "high": 2, "low": 1, "close": 2}],
        ), patch(
            "app.services.kline_service.get_stock_kline",
            side_effect=RuntimeError("upstream failed"),
        ):
            result = get_compare_kline(payload)

        self.assertEqual(len(result["series"]), 2)
        self.assertIsNone(result["series"][0]["error"])
        self.assertEqual(result["series"][1]["items"], [])
        self.assertIn("upstream failed", result["series"][1]["error"] or "")


if __name__ == "__main__":
    unittest.main()
