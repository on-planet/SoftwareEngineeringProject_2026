from __future__ import annotations

from pathlib import Path
import os
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.fetchers import events_client


class EventsRssResilienceTests(unittest.TestCase):
    def test_rsshub_bases_dedupes_and_preserves_order(self) -> None:
        with patch.dict(
            os.environ,
            {"RSSHUB_BASES": "https://a.example, https://b.example/ , https://a.example"},
            clear=False,
        ):
            self.assertEqual(
                events_client._rsshub_bases(),
                ["https://a.example", "https://b.example"],
            )

    def test_fetch_rss_with_fallback_uses_next_base_when_first_empty(self) -> None:
        urls = ["https://a.example/feed", "https://b.example/feed"]
        expected = [{"title": "ok", "link": "", "published_at": None}]
        with patch("etl.fetchers.events_client._fetch_rss", side_effect=[[], expected]):
            self.assertEqual(events_client._fetch_rss_with_fallback(urls), expected)

    def test_fetch_rss_with_fallback_uses_stale_cache_when_all_bases_fail(self) -> None:
        urls = ["https://a.example/feed", "https://b.example/feed"]
        stale = [{"title": "cached", "link": "", "published_at": None}]
        with patch("etl.fetchers.events_client._fetch_rss", return_value=[]), patch(
            "etl.fetchers.events_client._load_cache",
            side_effect=[stale, None],
        ):
            self.assertEqual(events_client._fetch_rss_with_fallback(urls), stale)


if __name__ == "__main__":
    unittest.main()
