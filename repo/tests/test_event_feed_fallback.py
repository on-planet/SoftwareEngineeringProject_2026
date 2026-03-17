from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

if "pydantic_settings" not in sys.modules:
    fake_module = types.ModuleType("pydantic_settings")

    class BaseSettings:  # pragma: no cover - import shim for tests
        def __init__(self, **kwargs):
            annotations: dict[str, object] = {}
            for cls in reversed(self.__class__.mro()):
                annotations.update(getattr(cls, "__annotations__", {}))
            for key in annotations:
                if key in kwargs:
                    value = kwargs[key]
                else:
                    value = getattr(self.__class__, key, None)
                setattr(self, key, value)

    fake_module.BaseSettings = BaseSettings
    sys.modules["pydantic_settings"] = fake_module

from app.schemas.event_timeline import EventTimelineItem
from app.services import event_feed_service, event_stats_service, event_timeline_service


class EventFeedFallbackTests(unittest.TestCase):
    def test_payload_to_items_includes_buyback_and_insider(self) -> None:
        payload = {
            "items": [
                {
                    "symbol": "000001.SZ",
                    "type": "report",
                    "title": "2025Q4业绩预告",
                    "date": date(2026, 3, 10),
                    "source": "Snowball Report",
                }
            ],
            "buyback": [
                {
                    "symbol": "00700.HK",
                    "date": date(2026, 3, 10),
                    "amount": 0,
                    "source": "RSSHub Xueqiu Announcement",
                }
            ],
            "insider": [
                {
                    "symbol": "600519.SH",
                    "date": date(2026, 3, 10),
                    "type": "增持",
                    "shares": 1000,
                    "source": "Snowball F10",
                }
            ],
        }

        items = event_feed_service._payload_to_items(payload)
        by_type = {item.type: item for item in items}

        self.assertEqual(len(items), 3)
        self.assertEqual(by_type["report"].title, "2025Q4业绩预告")
        self.assertEqual(by_type["buyback"].title, "股份回购披露")
        self.assertIn("高管持股变动", by_type["insider"].title)

    def test_load_or_backfill_event_feed_triggers_remote_job_when_store_is_empty(self) -> None:
        expected = [EventTimelineItem(symbol="000001.SZ", type="report", title="事件", date=date(2026, 3, 10))]

        with (
            patch.object(event_feed_service, "_load_cached_event_feed", return_value=None),
            patch.object(event_feed_service, "load_preloaded_event_feed", return_value=None),
            patch.object(event_feed_service, "_query_event_feed", side_effect=[[], [], expected]) as query_mock,
            patch.object(event_feed_service, "run_events_job") as backfill_mock,
            patch.object(event_feed_service, "_cache_event_feed") as cache_mock,
        ):
            items = event_feed_service.load_or_backfill_event_feed(object(), start=date(2026, 3, 10), end=date(2026, 3, 10))

        self.assertEqual(items, expected)
        self.assertEqual(query_mock.call_count, 3)
        backfill_mock.assert_called_once_with(date(2026, 3, 10), date(2026, 3, 10))
        cache_mock.assert_called_once()

    def test_load_or_backfill_event_feed_skips_remote_job_when_range_already_has_data(self) -> None:
        existing = [EventTimelineItem(symbol="600519.SH", type="report", title="已有事件", date=date(2026, 3, 10))]

        with (
            patch.object(event_feed_service, "_load_cached_event_feed", return_value=None),
            patch.object(event_feed_service, "load_preloaded_event_feed", return_value=None),
            patch.object(event_feed_service, "_query_event_feed", side_effect=[[], existing]) as query_mock,
            patch.object(event_feed_service, "run_events_job") as backfill_mock,
            patch.object(event_feed_service, "_cache_event_feed") as cache_mock,
        ):
            items = event_feed_service.load_or_backfill_event_feed(
                object(),
                symbols=["000001.SZ"],
                start=date(2026, 3, 10),
                end=date(2026, 3, 10),
            )

        self.assertEqual(items, [])
        self.assertEqual(query_mock.call_count, 2)
        backfill_mock.assert_not_called()
        cache_mock.assert_not_called()

    def test_load_or_backfill_event_feed_returns_cached_items_without_query(self) -> None:
        cached = [EventTimelineItem(symbol="00700.HK", type="announcement", title="cached-event", date=date(2026, 3, 11))]

        with (
            patch.object(event_feed_service, "_load_cached_event_feed", return_value=cached),
            patch.object(event_feed_service, "load_preloaded_event_feed") as preload_mock,
            patch.object(event_feed_service, "_query_event_feed") as query_mock,
            patch.object(event_feed_service, "run_events_job") as backfill_mock,
        ):
            items = event_feed_service.load_or_backfill_event_feed(object(), start=date(2026, 3, 11), end=date(2026, 3, 11))

        self.assertEqual(items, cached)
        preload_mock.assert_not_called()
        query_mock.assert_not_called()
        backfill_mock.assert_not_called()

    def test_event_stats_ignore_cached_empty_payloads(self) -> None:
        feed_items = [
            EventTimelineItem(symbol="000001.SZ", type="report", title="报告", date=date(2026, 3, 10)),
            EventTimelineItem(symbol="000001.SZ", type="buyback", title="回购", date=date(2026, 3, 10)),
            EventTimelineItem(symbol="00700.HK", type="insider", title="高管变动", date=date(2026, 3, 11)),
        ]

        with (
            patch.object(event_stats_service, "get_json", return_value={"by_date": [], "by_type": [], "by_symbol": []}),
            patch.object(event_stats_service, "load_or_backfill_event_feed", return_value=feed_items),
            patch.object(event_stats_service, "set_json") as set_json_mock,
        ):
            by_date, by_type, by_symbol = event_stats_service.get_event_stats(object())

        self.assertEqual([(item.date, item.count) for item in by_date], [(date(2026, 3, 10), 2), (date(2026, 3, 11), 1)])
        self.assertEqual([(item.type, item.count) for item in by_type], [("buyback", 1), ("insider", 1), ("report", 1)])
        self.assertEqual([(item.symbol, item.count) for item in by_symbol], [("000001.SZ", 2), ("00700.HK", 1)])
        set_json_mock.assert_called_once()

    def test_event_timeline_ignores_cached_empty_payloads(self) -> None:
        feed_items = [
            EventTimelineItem(symbol="00700.HK", type="buyback", title="回购", date=date(2026, 3, 9)),
            EventTimelineItem(symbol="000001.SZ", type="report", title="报告", date=date(2026, 3, 10)),
            EventTimelineItem(symbol="600519.SH", type="insider", title="变动", date=date(2026, 3, 11)),
        ]

        with (
            patch.object(event_timeline_service, "get_json", return_value={"items": [], "total": 0}),
            patch.object(event_timeline_service, "load_or_backfill_event_feed", return_value=feed_items),
            patch.object(event_timeline_service, "set_json") as set_json_mock,
        ):
            items, total = event_timeline_service.list_event_timeline(object(), limit=2, offset=0, sort="desc")

        self.assertEqual(total, 3)
        self.assertEqual([item.date for item in items], [date(2026, 3, 11), date(2026, 3, 10)])
        set_json_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
