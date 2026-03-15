from __future__ import annotations

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from etl.fetchers.snowball_client import normalize_index_symbol, supported_index_specs, to_snowball_symbol


class IndexSymbolSupportTests(unittest.TestCase):
    def test_new_a_share_index_aliases_resolve_to_canonical_symbol(self) -> None:
        self.assertEqual(normalize_index_symbol("SH000016"), "000016.SH")
        self.assertEqual(normalize_index_symbol("SH000300"), "000300.SH")
        self.assertEqual(normalize_index_symbol("SH000688"), "000688.SH")
        self.assertEqual(normalize_index_symbol("BJ899050"), "899050.BJ")

    def test_new_a_share_index_symbols_convert_back_to_snowball_symbol(self) -> None:
        self.assertEqual(to_snowball_symbol("000016.SH"), "SH000016")
        self.assertEqual(to_snowball_symbol("000300.SH"), "SH000300")
        self.assertEqual(to_snowball_symbol("000688.SH"), "SH000688")
        self.assertEqual(to_snowball_symbol("899050.BJ"), "BJ899050")

    def test_supported_index_specs_include_extended_a_share_indices(self) -> None:
        by_symbol = {item["symbol"]: item for item in supported_index_specs()}
        self.assertEqual(by_symbol["000016.SH"]["name"], "上证50")
        self.assertEqual(by_symbol["000300.SH"]["name"], "沪深300")
        self.assertEqual(by_symbol["000688.SH"]["name"], "科创50")
        self.assertEqual(by_symbol["899050.BJ"]["name"], "北证50")


if __name__ == "__main__":
    unittest.main()
