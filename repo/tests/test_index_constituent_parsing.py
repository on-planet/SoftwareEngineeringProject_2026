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
    @patch("etl.fetchers.index_constituent_client.ball")
    def test_prefers_security_code_over_generic_root_code(self, mock_ball: Mock) -> None:
        mock_ball.index_weight_top10.return_value = {
            "code": "500",
            "msg": "Success",
            "data": {
                "updateDate": "2026-03-16",
                "weightList": [
                    {
                        "rowNum": "1",
                        "indexCode": "000300",
                        "tradeDate": "20260316",
                        "securityCode": "600519",
                        "securityName": "Kweichow Moutai",
                        "marketNameEn": "Shanghai Exchange",
                        "weight": 7.92,
                    },
                    {
                        "rowNum": "2",
                        "indexCode": "000300",
                        "tradeDate": "20260316",
                        "securityCode": "300750",
                        "securityName": "CATL",
                        "marketNameEn": "Shenzhen Exchange",
                        "weight": 6.62,
                    },
                ],
            },
        }

        rows = get_index_constituents("000300.SH", date(2026, 3, 16))

        self.assertEqual([row["symbol"] for row in rows], ["600519.SH", "300750.SZ"])
        self.assertEqual(rows[0]["name"], "Kweichow Moutai")
        self.assertEqual(rows[0]["rank"], 1)
        self.assertEqual(rows[0]["source"], "Snowball")
        self.assertNotIn("00500.HK", {row["symbol"] for row in rows})

    @patch("etl.fetchers.index_constituent_client._load_public_index_constituents")
    @patch("etl.fetchers.index_constituent_client.ball")
    def test_falls_back_to_csi_public_weights_when_snowball_is_unavailable(self, mock_ball: Mock, mock_public_loader: Mock) -> None:
        mock_ball = None
        mock_public_loader.return_value = [
            {
                "index_symbol": "000300.SH",
                "symbol": "600519.SH",
                "date": date(2026, 3, 16),
                "weight": 0.0792,
                "name": "Kweichow Moutai",
                "rank": 1,
                "source": "CSI",
            }
        ]

        with patch("etl.fetchers.index_constituent_client.ball", None):
            rows = get_index_constituents("000300.SH", date(2026, 3, 16))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "600519.SH")
        self.assertEqual(rows[0]["source"], "CSI")
        mock_public_loader.assert_called_once_with("000300.SH", "000300", date(2026, 3, 16))

    def test_parses_csi_public_weight_sheet_rows(self) -> None:
        from etl.fetchers.index_constituent_client import _parse_public_weight_sheet

        rows = _parse_public_weight_sheet(
            "000300.SH",
            date(2026, 3, 16),
            [
                ["指数代码", "Index Code", "000300"],
                ["成份券代码Constituent Code", "成份券名称Constituent Name", "权重(%)weight"],
                ["600519", "贵州茅台", "7.92"],
                ["300750", "宁德时代", "6.62"],
            ],
        )

        self.assertEqual([row["symbol"] for row in rows], ["600519.SH", "300750.SZ"])
        self.assertAlmostEqual(rows[0]["weight"], 0.0792, places=6)
        self.assertEqual(rows[0]["name"], "贵州茅台")
        self.assertEqual(rows[0]["source"], "CSI")
        self.assertEqual(rows[1]["rank"], 2)

    def test_beijing_stock_codes_normalize_to_bj_market(self) -> None:
        self.assertEqual(etl_normalize_symbol("BJ430047"), "430047.BJ")
        self.assertEqual(etl_normalize_symbol("430047"), "430047.BJ")
        self.assertEqual(api_normalize_symbol("BJ430047"), "430047.BJ")
        self.assertEqual(api_normalize_symbol("430047"), "430047.BJ")


if __name__ == "__main__":
    unittest.main()
