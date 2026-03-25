from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
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
from app.models.macro import Macro
from app.services import macro_service


class MacroSnapshotServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add_all(
            [
                Macro(key="GDP:USA", date=date(2024, 1, 1), value=100.0, score=0.1),
                Macro(key="GDP:USA", date=date(2025, 1, 1), value=120.0, score=0.2),
                Macro(key="CPI:USA", date=date(2025, 2, 1), value=2.3, score=0.4),
                Macro(key="CPI:USA", date=date(2024, 12, 1), value=2.5, score=0.3),
            ]
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_list_macro_snapshot_returns_latest_row_per_key(self) -> None:
        with (
            patch.object(macro_service, "get_json", return_value=None),
            patch.object(macro_service, "set_json") as set_json_mock,
        ):
            items = macro_service.list_macro_snapshot(self.db)

        self.assertEqual(
            [(item["key"], item["date"]) for item in items],
            [("CPI:USA", "2025-02-01"), ("GDP:USA", "2025-01-01")],
        )
        self.assertGreaterEqual(set_json_mock.call_count, 1)

    def test_list_macro_snapshot_honors_as_of_cutoff(self) -> None:
        with (
            patch.object(macro_service, "get_json", return_value=None),
            patch.object(macro_service, "set_json"),
        ):
            items = macro_service.list_macro_snapshot(self.db, as_of=date(2024, 12, 31))

        self.assertEqual(
            [(item["key"], item["date"]) for item in items],
            [("CPI:USA", "2024-12-01"), ("GDP:USA", "2024-01-01")],
        )

    def test_list_macro_snapshot_uses_cached_payload_when_available(self) -> None:
        cached_payload = {
            "items": [
                {"key": "GDP:USA", "date": "2025-01-01", "value": 120.0, "score": 0.2},
            ]
        }

        with (
            patch.object(macro_service, "get_json", return_value=cached_payload),
            patch.object(macro_service, "set_json") as set_json_mock,
        ):
            items = macro_service.list_macro_snapshot(self.db)

        self.assertEqual(items, cached_payload["items"])
        set_json_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
