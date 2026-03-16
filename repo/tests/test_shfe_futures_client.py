from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.fetchers import futures_client


class ShfeFuturesClientTests(unittest.TestCase):
    def test_select_main_contract_prefers_higher_volume_then_open_interest(self) -> None:
        rows = [
            {
                "PRODUCTID": "cu_f",
                "DELIVERYMONTH": "2605",
                "VOLUME": 1200,
                "OPENINTEREST": 8000,
                "OPENPRICE": 100000,
                "HIGHESTPRICE": 100500,
                "LOWESTPRICE": 99500,
                "CLOSEPRICE": 100200,
            },
            {
                "PRODUCTID": "cu_f",
                "DELIVERYMONTH": "2604",
                "VOLUME": 1500,
                "OPENINTEREST": 7000,
                "OPENPRICE": 99900,
                "HIGHESTPRICE": 100300,
                "LOWESTPRICE": 99400,
                "CLOSEPRICE": 100100,
            },
        ]

        selected = futures_client._select_main_contract(rows)

        self.assertIsNotNone(selected)
        self.assertEqual(selected["DELIVERYMONTH"], "2604")

    def test_select_main_contract_skips_subtotals_and_non_target_products(self) -> None:
        rows = [
            {"PRODUCTID": "cu_f", "DELIVERYMONTH": "小计", "VOLUME": 999999},
            {"PRODUCTID": "sc_tas", "DELIVERYMONTH": "2604", "VOLUME": 999999},
            {"PRODUCTID": "cu_f", "DELIVERYMONTH": "2606", "VOLUME": 100, "OPENINTEREST": 50},
        ]

        selected = futures_client._select_main_contract(rows)

        self.assertIsNotNone(selected)
        self.assertEqual(selected["DELIVERYMONTH"], "2606")

    def test_get_futures_daily_maps_target_products_from_shfe_payload(self) -> None:
        payload = {
            "report_date": "20260313",
            "o_curinstrument": [
                {
                    "PRODUCTID": "cu_f",
                    "PRODUCTNAME": "铜",
                    "DELIVERYMONTH": "2604",
                    "VOLUME": 85149,
                    "OPENINTEREST": 190911,
                    "OPENPRICE": 101240,
                    "HIGHESTPRICE": 101250,
                    "LOWESTPRICE": 100080,
                    "CLOSEPRICE": 100310,
                    "SETTLEMENTPRICE": 100600,
                },
                {
                    "PRODUCTID": "cu_f",
                    "PRODUCTNAME": "铜",
                    "DELIVERYMONTH": "小计",
                    "VOLUME": 183195,
                },
                {
                    "PRODUCTID": "au_f",
                    "PRODUCTNAME": "黄金",
                    "DELIVERYMONTH": "2606",
                    "VOLUME": 3200,
                    "OPENINTEREST": 9000,
                    "OPENPRICE": 548.2,
                    "HIGHESTPRICE": 549.8,
                    "LOWESTPRICE": 545.1,
                    "CLOSEPRICE": 547.9,
                    "SETTLEMENTPRICE": 548.0,
                },
                {
                    "PRODUCTID": "fu_f",
                    "PRODUCTNAME": "燃料油",
                    "DELIVERYMONTH": "2605",
                    "VOLUME": 2200,
                    "OPENINTEREST": 8000,
                    "OPENPRICE": "",
                    "HIGHESTPRICE": "",
                    "LOWESTPRICE": "",
                    "CLOSEPRICE": "",
                    "SETTLEMENTPRICE": 3011,
                },
                {
                    "PRODUCTID": "zn_f",
                    "PRODUCTNAME": "锌",
                    "DELIVERYMONTH": "2604",
                    "VOLUME": 999999,
                    "OPENPRICE": 1,
                    "HIGHESTPRICE": 1,
                    "LOWESTPRICE": 1,
                    "CLOSEPRICE": 1,
                },
            ],
        }

        original_fetch = futures_client._fetch_daily_payload
        futures_client._fetch_daily_payload = lambda as_of: payload
        try:
            rows = futures_client.get_futures_daily(date(2026, 3, 13))
        finally:
            futures_client._fetch_daily_payload = original_fetch

        self.assertEqual([row["symbol"] for row in rows], ["CU", "AU", "FU"])
        self.assertEqual(rows[0]["date"], date(2026, 3, 13))
        self.assertEqual(rows[0]["contract_month"], "2604")
        self.assertEqual(rows[0]["close"], 100310.0)
        self.assertEqual(rows[1]["name"], "黄金")
        self.assertEqual(rows[2]["open"], 3011.0)
        self.assertEqual(rows[2]["high"], 3011.0)
        self.assertEqual(rows[2]["low"], 3011.0)
        self.assertEqual(rows[2]["settlement"], 3011.0)
        self.assertEqual(rows[2]["source"], "SHFE")

    def test_get_futures_weekly_uses_instrument_id_for_contract_month(self) -> None:
        payload = {
            "report_date": "20260313",
            "o_cursor": [
                {
                    "PRODUCTID": "cu_f",
                    "PRODUCT": "cu",
                    "INSTRUMENTID": "cuefp",
                    "VOLUME": 999999,
                    "OPENINTEREST": 0,
                    "OPENPRICE": 100830,
                    "HIGHESTPRICE": 101220,
                    "LOWESTPRICE": 100830,
                    "CLOSEPRICE": "",
                    "SETTLEMENTPRICE": "",
                },
                {
                    "PRODUCTID": "cu_f",
                    "PRODUCT": "cu",
                    "INSTRUMENTID": "cu2604",
                    "VOLUME": 559660,
                    "OPENINTEREST": 190911,
                    "OPENPRICE": 100250,
                    "HIGHESTPRICE": 101980,
                    "LOWESTPRICE": 98370,
                    "CLOSEPRICE": 100310,
                    "SETTLEMENTPRICE": 100600,
                    "TURNOVER": 2.81e7,
                },
                {
                    "PRODUCTID": "sc_f",
                    "PRODUCT": "sc",
                    "INSTRUMENTID": "sc2605",
                    "VOLUME": 142180,
                    "OPENINTEREST": 90121,
                    "OPENPRICE": 727.1,
                    "HIGHESTPRICE": 778.0,
                    "LOWESTPRICE": 724.0,
                    "CLOSEPRICE": 750.8,
                    "SETTLEMENTPRICE": 751.1,
                    "TURNOVER": 2273.9,
                },
                {
                    "PRODUCTID": "sc_f",
                    "PRODUCT": "sc",
                    "INSTRUMENTID": "sc小计",
                    "VOLUME": 9999999,
                },
            ],
        }

        original_fetch = futures_client._fetch_weekly_payload
        futures_client._fetch_weekly_payload = lambda as_of: payload
        try:
            rows = futures_client.get_futures_weekly(date(2026, 3, 13))
        finally:
            futures_client._fetch_weekly_payload = original_fetch

        self.assertEqual([row["symbol"] for row in rows], ["CU", "SC"])
        self.assertEqual(rows[0]["contract_month"], "2604")
        self.assertEqual(rows[1]["contract_month"], "2605")
        self.assertEqual(rows[1]["turnover"], 2273.9)


if __name__ == "__main__":
    unittest.main()
