from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import Mock, patch

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

from app.services.index_constituent_service import list_index_constituents


class IndexConstituentServiceTests(unittest.TestCase):
    @patch("app.services.index_constituent_service.list_live_index_constituents")
    def test_falls_back_to_database_when_live_result_is_empty(self, mock_live: Mock) -> None:
        mock_live.return_value = ([], 0)

        latest_date_result = Mock()
        latest_date_result.scalar.return_value = date(2026, 3, 15)

        total_result = Mock()
        total_result.scalar.return_value = 1

        rows_result = Mock()
        rows_result.mappings.return_value.all.return_value = [
            {
                "index_symbol": "000300.SH",
                "symbol": "600519.SH",
                "date": date(2026, 3, 15),
                "weight": 0.1234,
                "name": "Kweichow Moutai",
                "market": "A",
            }
        ]

        db = Mock()
        db.execute.side_effect = [latest_date_result, total_result, rows_result]

        items, total = list_index_constituents(db, "000300.SH", as_of=date(2026, 3, 16), limit=20, offset=0)

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["symbol"], "600519.SH")
        self.assertEqual(items[0]["source"], "DB")
        self.assertEqual(items[0]["rank"], 1)
        mock_live.assert_called_once_with("000300.SH", as_of=date(2026, 3, 16), limit=20, offset=0)


if __name__ == "__main__":
    unittest.main()
