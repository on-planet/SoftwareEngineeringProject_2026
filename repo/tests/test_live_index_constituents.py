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
from app.services.live_index_service import list_live_index_constituents


class LiveIndexConstituentTests(unittest.TestCase):
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

    @patch("app.services.live_index_service.set_json")
    @patch("app.services.live_index_service.get_json")
    @patch("app.services.live_index_service.get_stock_basics")
    @patch("app.services.live_index_service.get_index_constituents")
    def test_a_share_constituents_are_supported_and_enriched(
        self,
        mock_get_index_constituents,
        mock_get_stock_basics,
        mock_get_json,
        mock_set_json,
    ) -> None:
        as_of = date(2030, 1, 2)
        self._install_fake_cache(mock_get_json, mock_set_json)
        mock_get_index_constituents.return_value = [
            {
                "index_symbol": "000300.SH",
                "symbol": "600519.SH",
                "date": as_of,
                "weight": 0.1234,
            },
            {
                "index_symbol": "000300.SH",
                "symbol": "300750.SZ",
                "date": as_of,
                "weight": 0.0831,
            },
        ]
        mock_get_stock_basics.return_value = [
            {"symbol": "600519.SH", "name": "Kweichow Moutai", "market": "A", "sector": "Consumer Staples"},
            {"symbol": "300750.SZ", "name": "CATL", "market": "A", "sector": "Industrials"},
        ]

        items, total = list_live_index_constituents("000300.SH", as_of=as_of, limit=20, offset=0)

        self.assertEqual(total, 2)
        self.assertEqual(items[0]["symbol"], "600519.SH")
        self.assertEqual(items[0]["name"], "Kweichow Moutai")
        self.assertEqual(items[0]["market"], "A")
        self.assertEqual(items[0]["rank"], 1)
        self.assertEqual(items[0]["source"], "Snowball")
        self.assertEqual(items[1]["rank"], 2)
        mock_get_index_constituents.assert_called_once_with("000300.SH", as_of)
        mock_get_stock_basics.assert_called_once_with(["600519.SH", "300750.SZ"])

    @patch("app.services.live_index_service.set_json")
    @patch("app.services.live_index_service.get_json")
    @patch("app.services.live_index_service.get_stock_basics")
    @patch("app.services.live_index_service.get_hk_index_constituents")
    def test_hk_constituents_skip_extra_enrichment_and_reuse_cache_across_pages(
        self,
        mock_get_hk_index_constituents,
        mock_get_stock_basics,
        mock_get_json,
        mock_set_json,
    ) -> None:
        as_of = date(2030, 1, 3)
        self._install_fake_cache(mock_get_json, mock_set_json)
        mock_get_hk_index_constituents.return_value = [
            {
                "index_symbol": "HKHSI",
                "symbol": "00700.HK",
                "date": as_of,
                "weight": None,
                "name": "Tencent",
                "market": "HK",
                "rank": 1,
                "contribution_change": 12.5,
                "source": "Hang Seng Indexes",
            },
            {
                "index_symbol": "HKHSI",
                "symbol": "00941.HK",
                "date": as_of,
                "weight": None,
                "name": "China Mobile",
                "market": "HK",
                "rank": 2,
                "contribution_change": 8.0,
                "source": "Hang Seng Indexes",
            },
        ]

        first_page, first_total = list_live_index_constituents("HKHSI", as_of=as_of, limit=1, offset=0)
        second_page, second_total = list_live_index_constituents("HKHSI", as_of=as_of, limit=1, offset=1)

        self.assertEqual(first_total, 2)
        self.assertEqual(second_total, 2)
        self.assertEqual(first_page[0]["symbol"], "00700.HK")
        self.assertEqual(second_page[0]["symbol"], "00941.HK")
        self.assertEqual(mock_get_hk_index_constituents.call_count, 1)
        mock_get_stock_basics.assert_not_called()

    @patch("app.services.live_index_service.get_stock_basics")
    @patch("app.services.live_index_service.get_index_constituents")
    @patch("app.services.live_index_service.set_json")
    @patch("app.services.live_index_service.get_json")
    def test_empty_live_result_is_not_cached(
        self,
        mock_get_json,
        mock_set_json,
        mock_get_index_constituents,
        mock_get_stock_basics,
    ) -> None:
        as_of = date(2030, 1, 1)
        self._install_fake_cache(mock_get_json, mock_set_json)
        mock_get_index_constituents.side_effect = [
            [],
            [
                {
                    "index_symbol": "000300.SH",
                    "symbol": "600519.SH",
                    "date": as_of,
                    "weight": 0.1234,
                    "source": "CSI",
                }
            ],
        ]
        mock_get_stock_basics.return_value = [{"symbol": "600519.SH", "name": "Kweichow Moutai", "market": "A"}]

        first_items, first_total = list_live_index_constituents("000300.SH", as_of=as_of)
        second_items, second_total = list_live_index_constituents("000300.SH", as_of=as_of)

        self.assertEqual(first_total, 0)
        self.assertEqual(first_items, [])
        self.assertEqual(second_total, 1)
        self.assertEqual(second_items[0]["symbol"], "600519.SH")
        self.assertEqual(mock_get_index_constituents.call_count, 2)


if __name__ == "__main__":
    unittest.main()
