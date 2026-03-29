from __future__ import annotations

from datetime import date, datetime, timezone
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

from app.services.dashboard_service import get_dashboard_overview, get_dashboard_stats_overview


class DashboardServiceTests(unittest.TestCase):
    @patch("app.services.dashboard_service.set_json")
    @patch("app.services.dashboard_service.list_news_aggregate")
    @patch("app.services.dashboard_service.list_futures")
    @patch("app.services.dashboard_service.list_macro_snapshot")
    @patch("app.services.dashboard_service.get_heatmap")
    @patch("app.services.dashboard_service.get_cached_heatmap")
    @patch("app.services.dashboard_service.list_indices")
    @patch("app.services.dashboard_service.get_json")
    def test_get_dashboard_overview_builds_latest_snapshot_payload(
        self,
        mock_get_json,
        mock_list_indices,
        mock_get_cached_heatmap,
        mock_get_heatmap,
        mock_list_macro_snapshot,
        mock_list_futures,
        mock_list_news_aggregate,
        mock_set_json,
    ) -> None:
        mock_get_json.return_value = None
        mock_list_indices.return_value = [
            {"symbol": "000001.SH", "name": "上证指数", "market": "A", "date": date(2026, 3, 27), "close": 3200.0, "change": 12.0},
            {"symbol": "HSI", "name": "恒生指数", "market": "HK", "date": date(2026, 3, 27), "close": 17000.0, "change": -80.0},
        ]
        mock_get_cached_heatmap.side_effect = [
            [{"sector": "金融", "avg_close": 10.0, "avg_change": 0.5}],
            None,
        ]
        mock_get_heatmap.return_value = [{"sector": "科技", "avg_close": 20.0, "avg_change": -0.2}]
        mock_list_macro_snapshot.return_value = [
            {"key": "CPI", "date": date(2026, 3, 1), "value": 1.5, "score": 0.2},
        ]
        mock_list_futures.return_value = (
            [
                {"symbol": "AU", "date": date(2026, 3, 27), "close": 600.0, "open": 598.0},
                {"symbol": "AU", "date": date(2026, 3, 26), "close": 595.0, "open": 590.0},
                {"symbol": "CU", "date": date(2026, 3, 27), "close": 72000.0, "open": 71800.0},
            ],
            3,
        )
        mock_list_news_aggregate.return_value = (
            [
                {
                    "id": 1,
                    "symbol": "000001.SH",
                    "title": "示例新闻",
                    "sentiment": "positive",
                    "published_at": datetime(2026, 3, 27, 8, 0, tzinfo=timezone.utc),
                }
            ],
            12,
        )

        payload = get_dashboard_overview(Mock(), futures_limit=8, news_limit=8)

        self.assertEqual(payload["indices"]["total"], 2)
        self.assertEqual(payload["indices"]["items"][0]["symbol"], "000001.SH")
        self.assertEqual(payload["heatmap"]["a"]["items"][0]["sector"], "金融")
        self.assertEqual(payload["heatmap"]["hk"]["items"][0]["sector"], "科技")
        self.assertEqual(payload["macro_snapshot"]["items"][0]["key"], "CPI")
        self.assertEqual(payload["futures"]["total"], 2)
        self.assertEqual([item["symbol"] for item in payload["futures"]["items"]], ["AU", "CU"])
        self.assertEqual(payload["top_news"]["total"], 12)
        mock_set_json.assert_called_once()

    @patch("app.services.dashboard_service.get_news_stats")
    @patch("app.services.dashboard_service.get_event_stats")
    @patch("app.services.dashboard_service.get_json")
    def test_get_dashboard_stats_overview_returns_cached_payload(
        self,
        mock_get_json,
        mock_get_event_stats,
        mock_get_news_stats,
    ) -> None:
        mock_get_json.return_value = {
            "events": {
                "by_date": [{"date": "2026-03-27", "count": 3}],
                "by_type": [{"type": "earnings", "count": 2}],
                "by_symbol": [{"symbol": "000001.SH", "count": 1}],
            },
            "news": {
                "by_date": [{"date": "2026-03-27", "count": 5}],
                "by_sentiment": [{"sentiment": "positive", "count": 4}],
                "by_symbol": [{"symbol": "000001.SH", "count": 2}],
            },
        }

        payload = get_dashboard_stats_overview(Mock(), symbols=["000001.SH"], granularity="day")

        self.assertEqual(payload["events"]["by_date"][0]["count"], 3)
        self.assertEqual(payload["news"]["by_sentiment"][0]["sentiment"], "positive")
        mock_get_event_stats.assert_not_called()
        mock_get_news_stats.assert_not_called()


if __name__ == "__main__":
    unittest.main()
