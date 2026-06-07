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

from app.services import heatmap_service
from app.services.heatmap_service import get_cached_heatmap
from etl.jobs import sector_exposure_job
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

    def test_live_hk_heatmap_fallback_builds_from_provider_rows(self) -> None:
        basics = [
            {"symbol": "00700.HK", "market": "HK", "sector": "Technology"},
            {"symbol": "00005.HK", "market": "HK", "sector": "Finance"},
        ]
        daily_rows = [
            {"symbol": "00700.HK", "date": date(2026, 6, 1), "open": 100.0, "close": 105.0},
            {"symbol": "00005.HK", "date": date(2026, 6, 1), "open": 80.0, "close": 78.0},
        ]

        with patch.object(heatmap_service._provider.market, "get_stock_basic", return_value=basics), patch.object(
            heatmap_service._provider.market,
            "get_daily_prices",
            return_value=daily_rows,
        ):
            items = heatmap_service._build_live_market_heatmap("HK", date(2026, 6, 1))

        self.assertEqual(len(items), 2)
        self.assertEqual(sorted(item["avg_change"] for item in items), [-2.0, 5.0])

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

    def test_sector_exposure_job_upserts_stock_basics_and_fetches_missing_daily_rows(self) -> None:
        stock_rows = [{"symbol": "000001.SZ", "market": "A", "sector": "银行", "name": "平安银行"}]
        daily_rows = [
            {"symbol": "000001.SZ", "date": date(2026, 6, 1), "open": 10.0, "close": 11.0, "high": 11.0, "low": 10.0, "volume": 1.0}
        ]

        with patch.object(sector_exposure_job, "get_stock_basic", return_value=stock_rows), patch.object(
            sector_exposure_job, "get_daily_prices", return_value=daily_rows
        ) as daily_fetch, patch.object(
            sector_exposure_job, "market_data_session"
        ) as market_session, patch.object(
            sector_exposure_job, "list_daily_price_rows", return_value=[]
        ), patch.object(
            sector_exposure_job, "list_stock_valuation_rows", return_value=[]
        ), patch.object(
            sector_exposure_job, "_fetch_missing_valuation_snapshots", return_value=[]
        ), patch.object(
            sector_exposure_job, "upsert_stocks", return_value=1
        ) as upsert_stocks, patch.object(
            sector_exposure_job, "upsert_daily_prices", return_value=1
        ), patch.object(
            sector_exposure_job, "cache_heatmap"
        ) as cache_heatmap, patch.object(
            sector_exposure_job, "cache_sector_exposure"
        ), patch.object(
            sector_exposure_job, "upsert_sector_exposure", return_value=1
        ), patch.object(
            sector_exposure_job, "upsert_sector_exposure_summary", return_value=1
        ):
            market_session.return_value.__enter__.return_value = None
            market_session.return_value.__exit__.return_value = None
            total = sector_exposure_job.run_sector_exposure_job(date(2026, 6, 1), date(2026, 6, 1))

        upsert_stocks.assert_called_once_with(stock_rows)
        daily_fetch.assert_called_once()
        cache_heatmap.assert_called_once()


if __name__ == "__main__":
    unittest.main()
