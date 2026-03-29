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
    pydantic_settings = types.ModuleType("pydantic_settings")

    class BaseSettings:  # pragma: no cover - test shim for missing optional dependency
        pass

    pydantic_settings.BaseSettings = BaseSettings
    sys.modules["pydantic_settings"] = pydantic_settings

from app.core.cache import _memory_cache
from app.services.live_index_service import list_live_indices


class LiveIndicesTests(unittest.TestCase):
    def setUp(self) -> None:
        _memory_cache.clear()

    @staticmethod
    def _install_fake_cache(mock_get_json, mock_set_json) -> dict[str, list[dict]]:
        fake_cache: dict[str, list[dict]] = {}

        def _fake_get_json(key: str):
            return fake_cache.get(key)

        def _fake_set_json(key: str, payload, ttl=None) -> bool:
            del ttl
            fake_cache[key] = payload
            return True

        mock_get_json.side_effect = _fake_get_json
        mock_set_json.side_effect = _fake_set_json
        return fake_cache

    @patch("app.services.live_index_service.supported_index_specs")
    @patch("app.services.live_index_service.get_index_daily")
    @patch("app.services.live_index_service.set_json")
    @patch("app.services.live_index_service.get_json")
    def test_empty_live_indices_are_not_cached(
        self,
        mock_get_json,
        mock_set_json,
        mock_get_index_daily,
        mock_supported_index_specs,
    ) -> None:
        as_of = date(2030, 1, 2)
        self._install_fake_cache(mock_get_json, mock_set_json)
        mock_supported_index_specs.return_value = [
            {"symbol": "000300.SH", "name": "沪深300", "market": "A"},
        ]
        mock_get_index_daily.side_effect = [
            [],
            [{"symbol": "000300.SH", "date": as_of, "close": 3500.0, "change": 12.3}],
        ]

        first_items = list_live_indices(as_of=as_of)
        second_items = list_live_indices(as_of=as_of)

        self.assertEqual(first_items, [])
        self.assertEqual(len(second_items), 1)
        self.assertEqual(second_items[0]["symbol"], "000300.SH")
        self.assertEqual(mock_get_index_daily.call_count, 2)
        mock_set_json.assert_called_once()


if __name__ == "__main__":
    unittest.main()
