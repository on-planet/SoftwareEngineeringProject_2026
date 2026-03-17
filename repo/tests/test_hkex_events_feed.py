from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from etl.fetchers import events_client


class HkexEventsFeedTests(unittest.TestCase):
    def test_hkex_regulatory_announcements_feed_url(self) -> None:
        self.assertEqual(
            events_client._hkex_regulatory_announcements_rss(),
            "https://www.hkex.com.hk/Services/RSS-Feeds/regulatory-announcements?sc_lang=zh-HK",
        )

    def test_symbol_from_hkex_title_supports_common_patterns(self) -> None:
        self.assertEqual(
            events_client._symbol_from_hkex_title("股份代號：700 騰訊控股 公告"),
            "00700.HK",
        )
        self.assertEqual(
            events_client._symbol_from_hkex_title("(00005) 匯豐控股有限公司 - 公告"),
            "00005.HK",
        )
        self.assertEqual(
            events_client._symbol_from_hkex_title("00001 HKEX Sample Announcement"),
            "00001.HK",
        )

    def test_get_hkex_regulatory_announcements_builds_event_rows(self) -> None:
        fake_items = [
            {
                "title": "股份代號：700 騰訊控股 公告",
                "link": "https://www.hkex.com.hk/News/News-Release?newsid=123",
                "published_at": datetime(2026, 3, 16, 3, 0, tzinfo=timezone.utc),
            }
        ]
        with patch.object(events_client, "_fetch_rss", return_value=fake_items):
            rows = events_client._get_hkex_regulatory_announcements(date(2026, 3, 16))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "00700.HK")
        self.assertEqual(rows[0]["type"], "announcement")
        self.assertEqual(rows[0]["source"], "HKEX Regulatory Announcement")


if __name__ == "__main__":
    unittest.main()
