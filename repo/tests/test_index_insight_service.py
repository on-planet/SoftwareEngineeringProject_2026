from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

if "pydantic_settings" not in sys.modules:
    pydantic_settings = types.ModuleType("pydantic_settings")

    class BaseSettings:  # pragma: no cover - test shim for missing optional dependency
        pass

    pydantic_settings.BaseSettings = BaseSettings
    sys.modules["pydantic_settings"] = pydantic_settings

from app.core.cache import _memory_cache
from app.services.index_insight_service import get_index_insight


class IndexInsightServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        _memory_cache.clear()

    @patch("app.services.index_insight_service.list_index_constituents")
    @patch("app.services.index_insight_service.get_stock_quotes")
    def test_builds_summary_rankings_and_sector_breakdown(self, mock_get_stock_quotes: Mock, mock_list_index_constituents: Mock) -> None:
        mock_list_index_constituents.return_value = (
            [
                {"index_symbol": "000300.SH", "symbol": "600519.SH", "date": date(2026, 3, 26), "weight": 0.12, "name": "茅台", "market": "A"},
                {"index_symbol": "000300.SH", "symbol": "300750.SZ", "date": date(2026, 3, 26), "weight": 0.08, "name": "宁德时代", "market": "A"},
                {"index_symbol": "000300.SH", "symbol": "601318.SH", "date": date(2026, 3, 26), "weight": 0.05, "name": "中国平安", "market": "A"},
            ],
            3,
        )
        mock_get_stock_quotes.return_value = [
            {"symbol": "600519.SH", "name": "茅台", "market": "A", "sector": "Consumer Staples", "current": 1800.0, "change": 12.0, "percent": 0.67},
            {"symbol": "300750.SZ", "name": "宁德时代", "market": "A", "sector": "Tech", "current": 220.0, "change": 8.0, "percent": 3.2},
            {"symbol": "601318.SH", "name": "中国平安", "market": "A", "sector": "Financials", "current": 48.0, "change": -1.0, "percent": -2.0},
        ]

        payload = get_index_insight(Mock(), "000300.SH")

        self.assertEqual(payload["summary"]["constituent_total"], 3)
        self.assertEqual(payload["summary"]["priced_total"], 3)
        self.assertAlmostEqual(payload["summary"]["weight_coverage"], 0.25)
        self.assertEqual(payload["top_weights"][0]["symbol"], "600519.SH")
        self.assertEqual(payload["top_contributors"][0]["symbol"], "300750.SZ")
        self.assertEqual(payload["top_detractors"][0]["symbol"], "601318.SH")
        self.assertEqual(payload["sector_breakdown"][0]["sector"], "消费")
        self.assertEqual(payload["sector_breakdown"][1]["sector"], "科技")
        self.assertEqual(payload["constituents"][1]["sector"], "科技")


if __name__ == "__main__":
    unittest.main()
