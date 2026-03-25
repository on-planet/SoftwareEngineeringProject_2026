from __future__ import annotations

from datetime import date, datetime
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
from app.models.bond_market_quote import BondMarketQuote
from app.models.bond_market_trade import BondMarketTrade
from app.models.fx_quote import FxPairQuote, FxSpotQuote, FxSwapQuote
from app.models.stock_institute_hold import StockInstituteHold, StockInstituteHoldDetail
from app.models.stock_institute_recommend import StockInstituteRecommend, StockInstituteRecommendDetail
from app.models.stock_report_disclosure import StockReportDisclosure
from app.services import bond_market_service, stock_institute_service, stock_report_service


class ReferenceDataServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_list_bond_market_quotes_fetches_and_persists_when_empty(self) -> None:
        rows = [
            {
                "quote_org": "中金公司",
                "bond_name": "24国债01",
                "buy_net_price": 99.1,
                "sell_net_price": 99.2,
                "buy_yield": 2.01,
                "sell_yield": 2.0,
                "as_of": datetime(2026, 3, 24, 20, 0, 0),
                "source": "bond_spot_quote",
                "raw_json": "{}",
            }
        ]

        with patch.object(bond_market_service, "fetch_bond_market_quote_rows", return_value=rows) as fetch_mock:
            items, total = bond_market_service.list_bond_market_quotes(self.db)

        self.assertEqual(total, 1)
        self.assertEqual(items[0]["bond_name"], "24国债01")
        self.assertEqual(self.db.query(BondMarketQuote).count(), 1)
        fetch_mock.assert_called_once()

    def test_list_stock_institute_holds_fetches_requested_quarter(self) -> None:
        rows = [
            {
                "quarter": "20251",
                "symbol": "000001.SZ",
                "stock_name": "平安银行",
                "institute_count": 100.0,
                "institute_count_change": 5.0,
                "holding_ratio": 12.3,
                "holding_ratio_change": 0.4,
                "float_holding_ratio": 9.8,
                "float_holding_ratio_change": 0.2,
                "as_of": datetime(2026, 3, 24, 20, 0, 0),
                "source": "stock_institute_hold",
                "raw_json": "{}",
            }
        ]

        with patch.object(stock_institute_service, "fetch_stock_institute_hold_rows", return_value=rows) as fetch_mock:
            items, total, target_quarter = stock_institute_service.list_stock_institute_holds(
                self.db,
                quarter="20251",
            )

        self.assertEqual(target_quarter, "20251")
        self.assertEqual(total, 1)
        self.assertEqual(items[0]["symbol"], "000001.SZ")
        self.assertEqual(self.db.query(StockInstituteHold).count(), 1)
        fetch_mock.assert_called_once_with("20251")

    def test_list_stock_report_disclosures_fetches_requested_period(self) -> None:
        rows = [
            {
                "market": "沪深京",
                "period": "2025年报",
                "symbol": "000001.SZ",
                "stock_name": "平安银行",
                "first_booking": date(2026, 3, 10),
                "first_change": None,
                "second_change": None,
                "third_change": None,
                "actual_disclosure": date(2026, 3, 18),
                "as_of": datetime(2026, 3, 24, 20, 0, 0),
                "source": "stock_report_disclosure",
                "raw_json": "{\"股票代码\": \"000001\"}",
            }
        ]

        with patch.object(stock_report_service, "fetch_stock_report_disclosure_rows", return_value=rows) as fetch_mock:
            items, total, target_period = stock_report_service.list_stock_report_disclosures(
                self.db,
                market="沪深京",
                period="2025年报",
            )

        self.assertEqual(target_period, "2025年报")
        self.assertEqual(total, 1)
        self.assertEqual(items[0]["payload"]["股票代码"], "000001")
        self.assertEqual(self.db.query(StockReportDisclosure).count(), 1)
        fetch_mock.assert_called_once_with("沪深京", "2025年报")


if __name__ == "__main__":
    unittest.main()
