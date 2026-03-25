from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

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

from etl.fetchers import akshare_reference_client


class AkshareReferenceClientTests(unittest.TestCase):
    def test_fetch_bond_market_quote_rows_normalizes_fields(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "报价机构": "中金公司",
                    "债券简称": "24国债01",
                    "买入净价": "99.10",
                    "卖出净价": "99.20",
                    "买入收益率": "2.01",
                    "卖出收益率": "2.00",
                }
            ]
        )
        snapshot = datetime(2026, 3, 24, 20, 0, 0)

        with patch.object(
            akshare_reference_client,
            "_call_akshare_frame",
            return_value=(frame, "bond_spot_quote"),
        ):
            rows = akshare_reference_client.fetch_bond_market_quote_rows(as_of=snapshot)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["quote_org"], "中金公司")
        self.assertEqual(rows[0]["bond_name"], "24国债01")
        self.assertEqual(rows[0]["buy_net_price"], 99.10)
        self.assertEqual(rows[0]["sell_yield"], 2.00)
        self.assertEqual(rows[0]["as_of"], snapshot)
        self.assertEqual(rows[0]["source"], "bond_spot_quote")

    def test_fetch_stock_report_disclosure_rows_normalizes_dates_and_symbol(self) -> None:
        frame = pd.DataFrame(
            [
                {
                    "股票代码": "000001",
                    "股票简称": "平安银行",
                    "首次预约": date(2026, 3, 10),
                    "初次变更": None,
                    "二次变更": None,
                    "三次变更": None,
                    "实际披露": date(2026, 3, 18),
                }
            ]
        )

        with patch.object(
            akshare_reference_client,
            "_call_akshare_frame",
            return_value=(frame, "stock_report_disclosure"),
        ):
            rows = akshare_reference_client.fetch_stock_report_disclosure_rows("沪深京", "2025年报")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "000001.SZ")
        self.assertEqual(rows[0]["stock_name"], "平安银行")
        self.assertEqual(rows[0]["period"], "2025年报")
        self.assertEqual(rows[0]["actual_disclosure"], date(2026, 3, 18))


if __name__ == "__main__":
    unittest.main()
