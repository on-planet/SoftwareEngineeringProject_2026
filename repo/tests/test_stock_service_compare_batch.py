from __future__ import annotations

from pathlib import Path
import sys
import types
import unittest
from types import SimpleNamespace
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

from app.services.stock_service import get_stock_compare_batch


class StockServiceCompareBatchTests(unittest.TestCase):
    def test_compare_batch_uses_profile_service_for_missing_quote(self) -> None:
        db = MagicMock()
        stock = SimpleNamespace(symbol="000001.SZ", name="PingAn", market="A", sector="Financials")
        snapshot = None
        db.query.return_value.outerjoin.return_value.filter.return_value.all.return_value = [(stock, snapshot)]

        with patch(
            "app.services.stock_service.get_stock_overview_payload",
            return_value={
                "symbol": "000001.SZ",
                "name": "PingAn Live",
                "market": "A",
                "sector": "Financials",
                "quote": {"current": 11.2, "percent": 1.5},
            },
        ) as overview_mock:
            result = get_stock_compare_batch(db, ["000001.SZ"], prefer_live=True)

        self.assertEqual(result[0]["name"], "PingAn Live")
        self.assertEqual(result[0]["quote"]["current"], 11.2)
        overview_mock.assert_called_once_with("000001.SZ", prefer_live=True)

    def test_compare_batch_uses_profile_service_for_missing_symbol(self) -> None:
        db = MagicMock()
        db.query.return_value.outerjoin.return_value.filter.return_value.all.return_value = []

        with patch(
            "app.services.stock_service.get_stock_overview_payload",
            return_value={
                "symbol": "00700.HK",
                "name": "Tencent",
                "market": "HK",
                "sector": "Technology",
                "quote": {"current": 320.5},
            },
        ) as overview_mock:
            result = get_stock_compare_batch(db, ["00700.HK"], prefer_live=False)

        self.assertEqual(result[0]["symbol"], "00700.HK")
        self.assertEqual(result[0]["market"], "HK")
        self.assertEqual(result[0]["quote"]["current"], 320.5)
        overview_mock.assert_called_once_with("00700.HK", prefer_live=False)


if __name__ == "__main__":
    unittest.main()
