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
from app.services import event_feed_service, event_timeline_service


class EventTimelineNonBlockingTests(unittest.TestCase):
    def test_load_or_backfill_uses_async_mode_without_blocking_request(self) -> None:
        with (
            patch.object(event_feed_service, "_load_cached_event_feed", return_value=None),
            patch.object(event_feed_service, "load_preloaded_event_feed", return_value=None),
            patch.object(event_feed_service, "_query_event_feed", side_effect=[[], []]) as query_mock,
            patch.object(event_feed_service, "_schedule_remote_backfill", return_value=True) as schedule_mock,
            patch.object(event_feed_service, "run_events_job") as run_mock,
        ):
            items = event_feed_service.load_or_backfill_event_feed(
                object(),
                start=date(2026, 3, 16),
                end=date(2026, 3, 16),
                backfill_mode="async",
            )

        self.assertEqual(items, [])
        self.assertEqual(query_mock.call_count, 2)
        schedule_mock.assert_called_once_with(date(2026, 3, 16), date(2026, 3, 16))
        run_mock.assert_not_called()

    def test_event_timeline_service_requests_async_backfill(self) -> None:
        feed_items = [EventTimelineItem(symbol="000001.SZ", type="report", title="event", date=date(2026, 3, 16))]

        with (
            patch.object(event_timeline_service, "get_json", return_value={"items": [], "total": 0}),
            patch.object(event_timeline_service, "load_or_backfill_event_feed", return_value=feed_items) as load_mock,
            patch.object(event_timeline_service, "set_json"),
        ):
            items, total = event_timeline_service.list_event_timeline(object(), limit=20, offset=0, sort="desc")

        self.assertEqual(total, 1)
        self.assertEqual(items, feed_items)
        self.assertEqual(load_mock.call_args.kwargs["backfill_mode"], "async")


if __name__ == "__main__":
    unittest.main()
