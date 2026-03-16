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

from app.services.heatmap_service import get_cached_heatmap
from etl.jobs.sector_exposure_job import run_stock_valuation_backfill
from etl.transformers.heatmap import build_heatmap


class HeatmapAndValuationBackfillTests(unittest.TestCase):
    def test_build_heatmap_uses_normalized_sector_taxonomy(self) -> None:
        items = build_heatmap(
            [
                {"sector": "银行", "market": "A", "close": 10.0, "change": 1.0},
                {"sector": "J66货币金融服务", "market": "A", "close": 20.0, "change": 2.0},
                {"sector": "Software", "market": "US", "close": 30.0, "change": 3.0},
            ]
        )

        sectors = {(item["sector"], item["market"]) for item in items}
        self.assertIn(("金融", "A"), sectors)
        self.assertIn(("科技", "US"), sectors)

    def test_get_cached_heatmap_normalizes_cached_sector_names(self) -> None:
        payload = {
            "items": [
                {"sector": "Unknown", "market": "A", "avg_close": 1.0, "avg_change": 0.0, "close_sum": 1.0, "change_sum": 0.0, "count": 1},
                {"sector": "Software", "market": "US", "avg_close": 2.0, "avg_change": 0.5, "close_sum": 2.0, "change_sum": 0.5, "count": 1},
            ]
        }
        with patch("app.services.heatmap_service.get_json", return_value=payload):
            items = get_cached_heatmap()

        self.assertIsNotNone(items)
        self.assertEqual(items[0]["sector"], "科技")
        self.assertEqual(items[1]["sector"], "未分类")

    def test_run_stock_valuation_backfill_skips_stale_dates(self) -> None:
        with patch("etl.jobs.sector_exposure_job.get_stock_basic", return_value=[{"symbol": "000001.SZ"}]), patch(
            "etl.jobs.sector_exposure_job.market_data_session"
        ) as market_data_session, patch(
            "etl.jobs.sector_exposure_job._should_fetch_live_valuations",
            return_value=False,
        ), patch("etl.jobs.sector_exposure_job.list_daily_price_rows") as daily_rows, patch(
            "etl.jobs.sector_exposure_job._fetch_missing_valuation_snapshots"
        ) as fetch_snapshots:
            market_data_session.return_value.__enter__.return_value = None
            market_data_session.return_value.__exit__.return_value = None
            inserted = run_stock_valuation_backfill(date(2026, 1, 1), date(2026, 1, 1))

        self.assertEqual(inserted, 0)
        daily_rows.assert_not_called()
        fetch_snapshots.assert_not_called()


if __name__ == "__main__":
    unittest.main()
