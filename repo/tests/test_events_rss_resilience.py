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
    def test_fetch_rss_uses_stale_cache_when_download_fails(self) -> None:
        url = "https://www.hkex.com.hk/Services/RSS-Feeds/regulatory-announcements?sc_lang=zh-HK"
        stale = [{"title": "cached", "link": "", "published_at": None}]
        with patch("etl.fetchers.events_client._download_rss", return_value=None), patch(
            "etl.fetchers.events_client._load_cache",
            side_effect=[None, stale],
        ):
            self.assertEqual(events_client._fetch_rss(url), stale)

    def test_hkex_rss_url_is_configurable(self) -> None:
        with patch.dict(os.environ, {"HKEX_REGULATORY_ANNOUNCEMENTS_RSS": "https://example.com/hkex.xml"}):
            self.assertEqual(events_client._hkex_regulatory_announcements_rss(), "https://example.com/hkex.xml")

    def test_buyback_uses_hkex_feed(self) -> None:
        items = [
            {
                "title": "股份代號：700 騰訊控股 股份回購",
                "link": "https://www.hkex.com.hk/News/1",
                "published_at": __import__("datetime").datetime(2026, 3, 16, 3, 0, tzinfo=__import__("datetime").timezone.utc),
            }
        ]
        with patch("etl.fetchers.events_client._fetch_rss", return_value=items):
            rows = events_client.get_buyback(__import__("datetime").date(2026, 3, 16))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "00700.HK")
        self.assertEqual(rows[0]["source"], "HKEX Regulatory Announcement")


if __name__ == "__main__":
    unittest.main()
