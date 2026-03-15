from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from app.utils.symbols import symbol_lookup_aliases
from etl.fetchers.snowball_client import _normalize_search_row
from etl.utils.stock_basics_cache import _normalize_rows


class HongKongSymbolHandlingTests(unittest.TestCase):
    def test_search_row_maps_zero_padded_hk_code_back_to_hk(self) -> None:
        row = _normalize_search_row(
            {
                "code": "000700",
                "market": "HK",
                "name": "Tencent Holdings",
            }
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["symbol"], "00700.HK")
        self.assertEqual(row["market"], "HK")

    def test_cache_normalization_collapses_hk_variants_and_keeps_richer_metadata(self) -> None:
        rows = _normalize_rows(
            [
                {
                    "symbol": "0700.HK",
                    "name": "Tencent Holdings",
                    "market": "HK",
                    "sector": "Communication Services",
                },
                {
                    "symbol": "00700.HK",
                    "name": "00700.HK",
                    "market": "HK",
                    "sector": "Unknown",
                },
                {
                    "symbol": "0005.HK",
                    "name": "HSBC Holdings",
                    "market": "HK",
                    "sector": "Financial Services",
                },
            ]
        )
        by_symbol = {row["symbol"]: row for row in rows}
        self.assertEqual(by_symbol["00700.HK"]["name"], "Tencent Holdings")
        self.assertEqual(by_symbol["00700.HK"]["sector"], "Communication Services")
        self.assertIn("00005.HK", by_symbol)

    def test_symbol_lookup_aliases_cover_legacy_hk_widths(self) -> None:
        aliases = symbol_lookup_aliases("00700.HK")
        self.assertIn("700.HK", aliases)
        self.assertIn("0700.HK", aliases)
        self.assertIn("00700.HK", aliases)


if __name__ == "__main__":
    unittest.main()
