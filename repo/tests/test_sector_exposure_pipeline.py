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

from app.services.sector_exposure_service import get_sector_exposure
from etl.transformers.sector_exposure import build_sector_exposure
from etl.utils.sector_taxonomy import UNKNOWN_SECTOR, normalize_sector_name


class SectorExposurePipelineTests(unittest.TestCase):
    def test_sector_taxonomy_normalizes_unknown_and_groups_keywords(self) -> None:
        self.assertEqual(normalize_sector_name("Unknown"), UNKNOWN_SECTOR)
        self.assertEqual(normalize_sector_name("J66货币金融服务"), "金融")
        self.assertEqual(normalize_sector_name("Software"), "科技")
        self.assertEqual(normalize_sector_name("地产开发"), "房地产")

    def test_build_sector_exposure_uses_market_value_and_reports_coverage(self) -> None:
        payload = build_sector_exposure(
            [
                {"sector": "银行", "market": "A", "value": 100.0},
                {"sector": "Software", "market": "US", "value": 300.0},
                {"sector": "Unknown", "market": "HK", "value": None},
            ],
            basis="market_value",
        )

        self.assertEqual(payload["basis"], "market_value")
        self.assertEqual(payload["total_symbol_count"], 3)
        self.assertEqual(payload["covered_symbol_count"], 2)
        self.assertAlmostEqual(payload["coverage"], 2 / 3)
        self.assertEqual(payload["items"][0]["sector"], "科技")
        self.assertEqual(payload["items"][1]["sector"], "金融")
        self.assertAlmostEqual(payload["items"][0]["weight"], 0.75)

    def test_get_sector_exposure_returns_cached_metadata(self) -> None:
        cached_payload = {
            "date": "2026-03-16",
            "basis": "market_value",
            "total_value": 1000.0,
            "coverage": 0.8,
            "unknown_weight": 0.1,
            "items": [
                {"sector": "金融", "value": 400.0, "weight": 0.4, "symbol_count": 4},
                {"sector": "科技", "value": 600.0, "weight": 0.6, "symbol_count": 6},
            ],
        }
        with patch("app.services.sector_exposure_service.get_json", return_value=cached_payload):
            payload = get_sector_exposure(db=None, market="A", limit=None, offset=0, sort="desc", as_of=None, basis="market_value")

        self.assertEqual(payload.market, "A")
        self.assertEqual(payload.as_of, date(2026, 3, 16))
        self.assertEqual(payload.basis, "market_value")
        self.assertEqual(payload.total_value, 1000.0)
        self.assertAlmostEqual(payload.coverage, 0.8)
        self.assertAlmostEqual(payload.unknown_weight, 0.1)
        self.assertEqual(payload.items[0].sector, "科技")


if __name__ == "__main__":
    unittest.main()
