from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from app.routers.heatmap import get_heatmap_route


class HeatmapRouteCachePolicyTests(unittest.TestCase):
    def test_market_specific_request_bypasses_cache(self) -> None:
        paging = {"offset": 0, "limit": 20}
        sorting = {"sort": "desc"}
        db = object()
        live_rows = [{"sector": "Tech", "avg_close": 10.0, "avg_change": 1.0}]

        with patch("app.routers.heatmap.get_cached_heatmap", return_value=[{"sector": "stale"}]) as cached, patch(
            "app.routers.heatmap.get_heatmap", return_value=live_rows
        ) as live:
            result = get_heatmap_route(
                sector=None,
                market="HK",
                min_change=None,
                max_change=None,
                as_of=None,
                sorting=sorting,
                paging=paging,
                db=db,
            )

        cached.assert_not_called()
        live.assert_called_once_with(db, "desc", None, "HK", None, None, None)
        self.assertEqual(result["items"], live_rows)
        self.assertEqual(result["total"], 1)

    def test_market_none_prefers_cache(self) -> None:
        paging = {"offset": 0, "limit": 20}
        sorting = {"sort": "desc"}
        cached_rows = [{"sector": "Finance", "avg_close": 20.0, "avg_change": 2.0}]

        with patch("app.routers.heatmap.get_cached_heatmap", return_value=cached_rows) as cached, patch(
            "app.routers.heatmap.get_heatmap", return_value=[]
        ) as live:
            result = get_heatmap_route(
                sector=None,
                market=None,
                min_change=None,
                max_change=None,
                as_of=None,
                sorting=sorting,
                paging=paging,
                db=object(),
            )

        cached.assert_called_once_with(None, None, None, None, None, "desc")
        live.assert_not_called()
        self.assertEqual(result["items"], cached_rows)
        self.assertEqual(result["total"], 1)


if __name__ == "__main__":
    unittest.main()
