from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.utils import news_entities
from etl.utils.news_nlp import extract_news_nlp


class NewsNlpPipelineTests(unittest.TestCase):
    def tearDown(self) -> None:
        news_entities._alias_lookup.cache_clear()
        news_entities._symbol_sector_lookup.cache_clear()

    def test_extract_news_nlp_builds_entities_event_and_direction(self) -> None:
        rows = [
            {"symbol": "01211.HK", "name": "比亚迪", "market": "HK", "sector": "汽车"},
            {"symbol": "300750.SZ", "name": "宁德时代", "market": "A", "sector": "电池"},
        ]
        with patch("etl.utils.news_entities.load_stock_basics_cache", return_value=rows):
            result = extract_news_nlp(
                "比亚迪启动回购计划并拿下储能大单，新能源车板块走强",
                symbol="01211.HK",
                sentiment="positive",
            )

        self.assertIn("01211.HK", result.related_symbols)
        self.assertIn("工业制造", result.related_sectors)
        self.assertIn("新能源车", result.themes)
        self.assertEqual(result.event_type, "buyback")
        self.assertIn("buyback", result.event_tags)
        self.assertEqual(result.impact_direction, "positive")
        self.assertGreaterEqual(result.confidence, 0.5)
        self.assertTrue(result.keywords)

    def test_extract_news_nlp_marks_negative_policy_risk(self) -> None:
        rows = [
            {"symbol": "00700.HK", "name": "腾讯控股", "market": "HK", "sector": "互联网"},
        ]
        with patch("etl.utils.news_entities.load_stock_basics_cache", return_value=rows):
            result = extract_news_nlp(
                "腾讯遭遇监管调查并被罚款，游戏业务面临新限制",
                symbol="00700.HK",
                sentiment="negative",
            )

        self.assertEqual(result.event_type, "investigation")
        self.assertEqual(result.impact_direction, "negative")
        self.assertIn("regulation", result.event_tags)
        self.assertIn("00700.HK", result.related_symbols)


if __name__ == "__main__":
    unittest.main()
