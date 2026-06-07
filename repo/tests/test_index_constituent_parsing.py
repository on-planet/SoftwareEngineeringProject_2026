from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from app.utils.symbols import normalize_symbol as api_normalize_symbol
from etl.fetchers.index_constituent_client import get_index_constituents
from etl.fetchers.snowball_client import normalize_symbol as etl_normalize_symbol


class IndexConstituentParsingTests(unittest.TestCase):
    @patch("etl.fetchers.index_constituent_client.ak")
    def test_returns_akshare_constituents_when_available(self, mock_ak: Mock) -> None:
        import pandas as pd
        mock_ak.index_stock_cons_weight_csindex.return_value = pd.DataFrame({
            "成分券代码": ["600519", "300750"],
            "成分券名称": ["Kweichow Moutai", "CATL"],
            "权重": [7.92, 6.62],
        })

        rows = get_index_constituents("000300.SH", date(2026, 3, 16))

        self.assertEqual([row["symbol"] for row in rows], ["600519.SH", "300750.SZ"])
        self.assertEqual(rows[0]["name"], "Kweichow Moutai")
        self.assertEqual(rows[0]["rank"], 1)
        self.assertEqual(rows[0]["source"], "AkShare CSI")
        self.assertNotIn("00500.HK", {row["symbol"] for row in rows})

    @patch("etl.fetchers.index_constituent_client.ak")
    def test_returns_empty_when_akshare_unavailable(self, mock_ak: Mock) -> None:
        mock_ak.index_stock_cons_weight_csindex.side_effect = RuntimeError("network error")

        rows = get_index_constituents("000300.SH", date(2026, 3, 16))

        self.assertEqual(rows, [])

    def test_beijing_stock_codes_normalize_to_bj_market(self) -> None:
        self.assertEqual(etl_normalize_symbol("BJ430047"), "430047.BJ")
        self.assertEqual(etl_normalize_symbol("430047"), "430047.BJ")
        self.assertEqual(api_normalize_symbol("BJ430047"), "430047.BJ")
        self.assertEqual(api_normalize_symbol("430047"), "430047.BJ")


if __name__ == "__main__":
    unittest.main()
