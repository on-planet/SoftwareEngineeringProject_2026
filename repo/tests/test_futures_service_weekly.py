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

    class BaseSettings:
        def __init__(self, **kwargs):
            annotations: dict[str, object] = {}
            for cls in reversed(self.__class__.mro()):
                annotations.update(getattr(cls, "__annotations__", {}))
            for key in annotations:
                setattr(self, key, kwargs.get(key, getattr(self.__class__, key, None)))

    fake_module.BaseSettings = BaseSettings
    sys.modules["pydantic_settings"] = fake_module

from app.services import futures_service


class FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *args, **kwargs):
        return self

    def count(self):
        return len(self.rows)

    def order_by(self, *args, **kwargs):
        return self

    def offset(self, value):
        self.rows = self.rows[value:]
        return self

    def limit(self, value):
        self.rows = self.rows[:value]
        return self

    def all(self):
        return list(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self, rows):
        self.rows = rows

    def query(self, model):
        return FakeQuery(self.rows)


class FuturesServiceWeeklyTests(unittest.TestCase):
    def test_list_futures_weekly_uses_shfe_snapshot(self) -> None:
        rows = [
            {"symbol": "SC", "date": date(2026, 3, 13), "contract_month": "2605"},
            {"symbol": "CU", "date": date(2026, 3, 13), "contract_month": "2604"},
        ]
        with (
            patch.object(futures_service, "get_json", return_value=None),
            patch.object(futures_service, "get_futures_weekly", return_value=rows) as weekly_mock,
            patch.object(futures_service, "set_json") as set_json_mock,
        ):
            items, total = futures_service.list_futures(FakeSession([]), frequency="week", as_of=date(2026, 3, 13), sort="asc")

        weekly_mock.assert_called_once_with(date(2026, 3, 13))
        self.assertEqual(total, 2)
        self.assertEqual([item["symbol"] for item in items], ["CU", "SC"])
        set_json_mock.assert_called_once()

    def test_get_futures_series_weekly_builds_series_across_weeks(self) -> None:
        snapshots = {
            date(2026, 3, 6): [{"symbol": "AU", "date": date(2026, 3, 6), "contract_month": "2606"}],
            date(2026, 3, 13): [{"symbol": "AU", "date": date(2026, 3, 13), "contract_month": "2606"}],
        }

        def fake_weekly(as_of: date):
            return snapshots.get(as_of, [])

        with (
            patch.object(futures_service, "get_json", return_value=None),
            patch.object(futures_service, "get_futures_weekly", side_effect=fake_weekly),
            patch.object(futures_service, "set_json") as set_json_mock,
        ):
            items = futures_service.get_futures_series(
                FakeSession([]),
                "AU",
                start=date(2026, 3, 6),
                end=date(2026, 3, 13),
                frequency="week",
            )

        self.assertEqual([item["date"] for item in items], [date(2026, 3, 6), date(2026, 3, 13)])
        self.assertTrue(all(item["contract_month"] == "2606" for item in items))
        set_json_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
