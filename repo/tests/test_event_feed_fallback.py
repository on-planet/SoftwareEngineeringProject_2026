from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

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

from app.models.base import Base
from app.models.buyback import Buyback
from app.models.events import Event
from app.models.insider_trade import InsiderTrade
from app.schemas.event_timeline import EventTimelineItem
from app.services import event_feed_service, event_stats_service, event_timeline_service


class EventFeedFallbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def _seed_event_rows(self) -> None:
        self.db.add_all(
            [
                Event(
                    symbol="600519.SH",
                    type="report",
                    title="\u5b63\u5ea6\u62a5\u544a",
                    date=date(2026, 3, 11),
                    source="Event Feed",
                ),
                Buyback(
                    symbol="000001.SZ",
                    date=date(2026, 3, 10),
                    amount=0,
                ),
                InsiderTrade(
                    symbol="00700.HK",
                    date=date(2026, 3, 9),
                    type="\u589e\u6301",
                    shares=1000,
                ),
            ]
        )
        self.db.commit()

    def test_payload_to_items_includes_buyback_and_insider(self) -> None:
        payload = {
            "items": [
                {
                    "symbol": "000001.SZ",
                    "type": "report",
                    "title": "2025Q4\u4e1a\u7ee9\u9884\u544a",
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
                    "type": "\u589e\u6301",
                    "shares": 1000,
                    "source": "Snowball F10",
                }
            ],
        }

        items = event_feed_service._payload_to_items(payload)
        by_type = {item.type: item for item in items}

        self.assertEqual(len(items), 3)
        self.assertEqual(by_type["report"].title, "2025Q4\u4e1a\u7ee9\u9884\u544a")
        self.assertEqual(by_type["buyback"].title, "\u80a1\u4efd\u56de\u8d2d\u62ab\u9732")
        self.assertIn("\u9ad8\u7ba1\u6301\u80a1\u53d8\u52a8", by_type["insider"].title)

    def test_load_or_backfill_event_feed_triggers_remote_job_when_store_is_empty(self) -> None:
        expected = [EventTimelineItem(symbol="000001.SZ", type="report", title="\u4e8b\u4ef6", date=date(2026, 3, 10))]

        with (
            patch.object(event_feed_service, "_load_cached_event_feed", return_value=None),
            patch.object(event_feed_service, "load_preloaded_event_feed", return_value=None),
            patch.object(event_feed_service, "_query_event_feed_preview", side_effect=[([], 0), (expected, len(expected))]) as query_mock,
            patch.object(event_feed_service, "_event_feed_exists", return_value=False),
            patch.object(event_feed_service, "run_events_job") as backfill_mock,
            patch.object(event_feed_service, "_cache_event_feed") as cache_mock,
        ):
            items = event_feed_service.load_or_backfill_event_feed(
                object(),
                start=date(2026, 3, 10),
                end=date(2026, 3, 10),
                backfill_mode="sync",
            )

        self.assertEqual(items, expected)
        self.assertEqual(query_mock.call_count, 2)
        backfill_mock.assert_called_once_with(date(2026, 3, 10), date(2026, 3, 10))
        cache_mock.assert_called_once()

    def test_load_or_backfill_event_feed_does_not_trigger_remote_job_by_default(self) -> None:
        with (
            patch.object(event_feed_service, "_load_cached_event_feed", return_value=None),
            patch.object(event_feed_service, "load_preloaded_event_feed", return_value=None),
            patch.object(event_feed_service, "_query_event_feed_preview", return_value=([], 0)),
            patch.object(event_feed_service, "_event_feed_exists", return_value=False),
            patch.object(event_feed_service, "run_events_job") as backfill_mock,
            patch.object(event_feed_service, "_schedule_remote_backfill") as schedule_mock,
        ):
            items = event_feed_service.load_or_backfill_event_feed(
                object(),
                start=date(2026, 3, 10),
                end=date(2026, 3, 10),
            )

        self.assertEqual(items, [])
        backfill_mock.assert_not_called()
        schedule_mock.assert_not_called()

    def test_load_or_backfill_event_feed_skips_remote_job_when_range_already_has_data(self) -> None:
        with (
            patch.object(event_feed_service, "_load_cached_event_feed", return_value=None),
            patch.object(event_feed_service, "load_preloaded_event_feed", return_value=None),
            patch.object(event_feed_service, "_query_event_feed_preview", return_value=([], 0)),
            patch.object(event_feed_service, "_event_feed_exists", return_value=True),
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
        backfill_mock.assert_not_called()
        cache_mock.assert_not_called()

    def test_load_or_backfill_event_feed_returns_cached_items_without_query(self) -> None:
        cached = [EventTimelineItem(symbol="00700.HK", type="announcement", title="cached-event", date=date(2026, 3, 11))]

        with (
            patch.object(event_feed_service, "_load_cached_event_feed", return_value=cached),
            patch.object(event_feed_service, "load_preloaded_event_feed") as preload_mock,
            patch.object(event_feed_service, "_query_event_feed_preview") as query_mock,
            patch.object(event_feed_service, "run_events_job") as backfill_mock,
        ):
            items = event_feed_service.load_or_backfill_event_feed(object(), start=date(2026, 3, 11), end=date(2026, 3, 11))

        self.assertEqual(items, cached)
        preload_mock.assert_not_called()
        query_mock.assert_not_called()
        backfill_mock.assert_not_called()

    def test_event_stats_ignore_cached_empty_payloads(self) -> None:
        self.db.add_all(
            [
                Event(symbol="000001.SZ", type="report", title="\u62a5\u544a", date=date(2026, 3, 10), source="Event Feed"),
                Buyback(symbol="000001.SZ", date=date(2026, 3, 10), amount=0),
                InsiderTrade(symbol="00700.HK", date=date(2026, 3, 11), type="\u589e\u6301", shares=1000),
            ]
        )
        self.db.commit()

        with (
            patch.object(event_stats_service, "get_json", return_value={"by_date": [], "by_type": [], "by_symbol": []}),
            patch.object(event_feed_service, "run_events_job") as run_mock,
            patch.object(event_stats_service, "set_json") as set_json_mock,
        ):
            by_date, by_type, by_symbol = event_stats_service.get_event_stats(self.db)

        self.assertEqual([(item.date, item.count) for item in by_date], [(date(2026, 3, 10), 2), (date(2026, 3, 11), 1)])
        self.assertEqual([(item.type, item.count) for item in by_type], [("buyback", 1), ("insider", 1), ("report", 1)])
        self.assertEqual([(item.symbol, item.count) for item in by_symbol], [("000001.SZ", 2), ("00700.HK", 1)])
        run_mock.assert_not_called()
        set_json_mock.assert_called_once()

    def test_event_timeline_ignores_cached_empty_payloads(self) -> None:
        self._seed_event_rows()

        with (
            patch.object(event_timeline_service, "get_json", return_value={"items": [], "total": 0}),
            patch.object(event_timeline_service, "set_json") as set_json_mock,
        ):
            items, total = event_timeline_service.list_event_timeline(
                self.db,
                limit=2,
                offset=0,
                sort="desc",
                start=date(2026, 3, 9),
                end=date(2026, 3, 11),
            )

        self.assertEqual(total, 3)
        self.assertEqual([item.date for item in items], [date(2026, 3, 11), date(2026, 3, 10)])
        set_json_mock.assert_called_once()

    def test_list_event_feed_page_applies_sql_sort_and_pagination(self) -> None:
        self._seed_event_rows()

        with patch.object(event_feed_service, "count_event_feed_rows", side_effect=AssertionError("unexpected count query")):
            items, total = event_feed_service.list_event_feed_page(
                self.db,
                start=date(2026, 3, 9),
                end=date(2026, 3, 11),
                sort_by=["date"],
                sort="desc",
                limit=2,
                offset=1,
            )

        self.assertEqual(total, 3)
        self.assertEqual([(item.symbol, item.type) for item in items], [("000001.SZ", "buyback"), ("00700.HK", "insider")])

    def test_query_event_feed_preview_uses_bounded_limit(self) -> None:
        with patch.object(event_feed_service, "list_event_feed_page", return_value=([], 0)) as list_mock:
            event_feed_service._query_event_feed_preview(self.db)

        self.assertEqual(list_mock.call_args.kwargs["limit"], event_feed_service.EVENT_FEED_QUERY_LIMIT)

    def test_build_event_feed_source_casts_union_columns_for_postgres(self) -> None:
        source = event_feed_service._build_event_feed_source()
        self.assertIsNotNone(source)

        sql = str(select(source).compile(dialect=postgresql.dialect()))

        self.assertIn("CAST(events.symbol AS VARCHAR)", sql)
        self.assertIn("CAST(NULL AS FLOAT) AS amount", sql)
        self.assertIn("CAST(NULL AS VARCHAR) AS raw_type", sql)
        self.assertIn("CAST(NULL AS FLOAT) AS shares", sql)
        self.assertIn("CAST(buyback.amount AS FLOAT)", sql)
        self.assertIn("CAST(insider_trade.type AS VARCHAR)", sql)
        self.assertIn("CAST(insider_trade.shares AS FLOAT)", sql)


if __name__ == "__main__":
    unittest.main()
