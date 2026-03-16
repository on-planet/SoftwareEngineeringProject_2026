from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from etl.fetchers import news_client
from etl.utils.news_taxonomy import classify_news_metadata, classify_time_bucket


class NewsTaxonomyTests(unittest.TestCase):
    def test_external_market_feeds_are_registered(self) -> None:
        feeds = news_client._external_market_feeds()
        self.assertIn("https://quanwenrss.com/caixin/economy", feeds)
        self.assertIn("https://quanwenrss.com/morganstanley/global", feeds)
        self.assertIn("https://quanwenrss.com/apnews/world", feeds)
        self.assertIn("https://quanwenrss.com/politico/finance", feeds)

    def test_classify_external_feed_metadata_from_source_name(self) -> None:
        metadata = classify_news_metadata(
            source="Morgan Stanley Global",
            link="https://www.morganstanley.com/ideas/example",
            published_at=datetime(2026, 3, 16, 2, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(metadata["source_site"], "Morgan Stanley")
        self.assertEqual(metadata["source_category"], "investment_research")
        self.assertEqual(metadata["topic_category"], "global_markets")
        self.assertEqual(metadata["time_bucket"], "trading_hours")

    def test_classify_time_bucket_marks_weekend(self) -> None:
        bucket = classify_time_bucket(datetime(2026, 3, 15, 4, 0, tzinfo=timezone.utc))
        self.assertEqual(bucket, "weekend")


if __name__ == "__main__":
    unittest.main()
