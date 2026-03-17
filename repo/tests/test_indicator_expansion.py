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

from app.services.live_market_service import get_live_indicator_series


class IndicatorExpansionTests(unittest.TestCase):
    def test_ma_series_keeps_single_value_compatibility(self) -> None:
        rows = [
            {"date": date(2026, 3, 10), "open": 10.0, "high": 10.2, "low": 9.8, "close": 10.0, "volume": 100.0},
            {"date": date(2026, 3, 11), "open": 10.1, "high": 10.4, "low": 10.0, "close": 10.2, "volume": 120.0},
            {"date": date(2026, 3, 12), "open": 10.2, "high": 10.6, "low": 10.1, "close": 10.4, "volume": 140.0},
        ]
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._load_db_daily_rows", return_value=rows
        ), patch("app.services.live_market_service.set_json"):
            items, lines, params, cache_hit = get_live_indicator_series("000001.SZ", "ma", window=2, limit=10)

        self.assertFalse(cache_hit)
        self.assertEqual(lines, ["ma"])
        self.assertEqual(params, {"window": 2})
        self.assertEqual(items[-1].values["ma"], items[-1].value)

    def test_macd_returns_multi_line_payload(self) -> None:
        rows = [
            {"date": date(2026, 3, 10), "open": 10.0, "high": 10.2, "low": 9.8, "close": 10.0, "volume": 100.0},
            {"date": date(2026, 3, 11), "open": 10.1, "high": 10.5, "low": 10.0, "close": 10.4, "volume": 130.0},
            {"date": date(2026, 3, 12), "open": 10.4, "high": 10.8, "low": 10.3, "close": 10.7, "volume": 160.0},
            {"date": date(2026, 3, 13), "open": 10.8, "high": 11.0, "low": 10.7, "close": 10.9, "volume": 180.0},
        ]
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._load_db_daily_rows", return_value=rows
        ), patch("app.services.live_market_service.set_json"):
            items, lines, params, cache_hit = get_live_indicator_series("000001.SZ", "macd", window=14, limit=10)

        self.assertFalse(cache_hit)
        self.assertEqual(lines, ["macd", "signal", "hist"])
        self.assertEqual(params, {"fast": 12, "slow": 26, "signal": 9})
        self.assertTrue({"macd", "signal", "hist"}.issubset(items[-1].values.keys()))

    def test_obv_uses_volume_series(self) -> None:
        rows = [
            {"date": date(2026, 3, 10), "open": 10.0, "high": 10.2, "low": 9.8, "close": 10.0, "volume": 100.0},
            {"date": date(2026, 3, 11), "open": 10.0, "high": 10.6, "low": 9.9, "close": 10.5, "volume": 150.0},
            {"date": date(2026, 3, 12), "open": 10.5, "high": 10.7, "low": 10.1, "close": 10.2, "volume": 120.0},
        ]
        with patch("app.services.live_market_service.get_json", return_value=None), patch(
            "app.services.live_market_service._load_db_daily_rows", return_value=rows
        ), patch("app.services.live_market_service.set_json"):
            items, lines, params, _ = get_live_indicator_series("000001.SZ", "obv", window=14, limit=10)

        self.assertEqual(lines, ["obv"])
        self.assertEqual(params, {})
        self.assertEqual([item.values["obv"] for item in items], [0.0, 150.0, 30.0])


if __name__ == "__main__":
    unittest.main()
