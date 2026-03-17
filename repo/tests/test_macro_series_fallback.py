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

from app.services import macro_service


class FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def all(self):
        return list(self.rows)


class FakeSession:
    def __init__(self, rows):
        self.rows = rows

    def query(self, model):
        return FakeQuery(self.rows)


class MacroSeriesFallbackTests(unittest.TestCase):
    def test_parse_world_bank_series_key_accepts_supported_pairs(self) -> None:
        self.assertEqual(macro_service._parse_world_bank_series_key("gdp:usa"), ("GDP", "USA"))
        self.assertEqual(macro_service._parse_world_bank_series_key("UNEMP:CHN"), ("UNEMP", "CHN"))
        self.assertIsNone(macro_service._parse_world_bank_series_key("SHIBOR"))
        self.assertIsNone(macro_service._parse_world_bank_series_key("GDP:XXX"))

    def test_get_macro_series_does_not_refetch_world_bank_key_by_default(self) -> None:
        db = FakeSession([])

        with (
            patch.object(macro_service, "get_json", return_value=[]),
            patch.object(macro_service, "_fetch_world_bank_series_rows") as fetch_mock,
            patch.object(macro_service, "set_json") as set_json_mock,
        ):
            items = macro_service.get_macro_series(db, "GDP:USA")

        self.assertEqual(items, [])
        fetch_mock.assert_not_called()
        set_json_mock.assert_called_once()

    def test_get_macro_series_refetches_world_bank_key_when_sync_fetch_enabled(self) -> None:
        db = FakeSession([])
        fetched_rows = [
            {"key": "GDP:USA", "date": date(2024, 1, 1), "value": 120.0, "score": 0.3},
            {"key": "GDP:USA", "date": date(2023, 1, 1), "value": 100.0, "score": 0.2},
        ]

        with (
            patch.object(macro_service, "WORLD_BANK_SYNC_FETCH_ENABLED", True),
            patch.object(macro_service, "get_json", return_value=[]),
            patch.object(macro_service, "_fetch_world_bank_series_rows", return_value=fetched_rows) as fetch_mock,
            patch.object(macro_service, "_upsert_macro_rows") as upsert_mock,
            patch.object(macro_service, "set_json") as set_json_mock,
        ):
            items = macro_service.get_macro_series(db, "GDP:USA")

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].date, date(2023, 1, 1))
        self.assertEqual(items[1].value, 120.0)
        fetch_mock.assert_called_once_with("GDP:USA", start=None, end=None)
        upsert_mock.assert_called_once_with(db, fetched_rows)
        set_json_mock.assert_called_once()

    def test_get_macro_series_sorts_cached_rows_by_date_ascending(self) -> None:
        db = FakeSession([])
        cached_rows = [
            {"date": date(2024, 1, 1), "value": 120.0, "score": 0.3},
            {"date": date(2023, 1, 1), "value": 100.0, "score": 0.2},
        ]

        with patch.object(macro_service, "get_json", return_value=cached_rows):
            items = macro_service.get_macro_series(db, "GDP:USA")

        self.assertEqual([item.date for item in items], [date(2023, 1, 1), date(2024, 1, 1)])

    def test_get_macro_series_does_not_refetch_unsupported_key(self) -> None:
        db = FakeSession([])

        with (
            patch.object(macro_service, "get_json", return_value=[]),
            patch.object(macro_service, "_fetch_world_bank_series_rows") as fetch_mock,
            patch.object(macro_service, "set_json") as set_json_mock,
        ):
            items = macro_service.get_macro_series(db, "SHIBOR")

        self.assertEqual(items, [])
        fetch_mock.assert_not_called()
        set_json_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
