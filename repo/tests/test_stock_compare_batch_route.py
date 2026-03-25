from __future__ import annotations

from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

if "pydantic_settings" not in sys.modules:
    fake_module = types.ModuleType("pydantic_settings")

    class BaseSettings:
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

from app.routers.stock import get_stock_compare_batch_route
from app.schemas.stock import StockCompareBatchIn


class StockCompareBatchRouteTests(unittest.TestCase):
    def test_route_wraps_service_payload(self) -> None:
        payload = StockCompareBatchIn(symbols=["000001.SZ", "00700.HK"], prefer_live=True)

        with patch(
            "app.routers.stock.get_stock_compare_batch",
            return_value=[
                {
                    "symbol": "000001.SZ",
                    "name": "平安银行",
                    "market": "A",
                    "sector": "金融",
                    "quote": {"current": 11.2, "percent": 1.5},
                    "error": None,
                },
                {
                    "symbol": "00700.HK",
                    "name": "腾讯控股",
                    "market": "HK",
                    "sector": "互联网",
                    "quote": None,
                    "error": "Stock not found",
                },
            ],
        ) as service_mock:
            result = get_stock_compare_batch_route(payload, db=MagicMock())

        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0].symbol, "000001.SZ")
        self.assertEqual(result["items"][0].quote.current, 11.2)
        self.assertEqual(result["items"][1].error, "Stock not found")
        service_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
