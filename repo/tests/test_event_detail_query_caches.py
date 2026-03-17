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

from app.schemas.buyback import BuybackOut
from app.schemas.insider_trade import InsiderTradeOut
from app.services import buyback_service, insider_trade_service


class DummyDb:
    def __init__(self, query_obj):
        self._query_obj = query_obj

    def query(self, _model):
        return self._query_obj


class GuardDb:
    def query(self, _model):  # pragma: no cover - should not be reached
        raise AssertionError("db.query should not be called on cache hit")


class FakeBuybackQuery:
    def __init__(self, items, total):
        self._items = items
        self._total = total

    def filter(self, *_args, **_kwargs):
        return self

    def count(self):
        return self._total

    def order_by(self, *_args, **_kwargs):
        return self

    def offset(self, _offset):
        return self

    def limit(self, _limit):
        return self

    def all(self):
        return self._items


class FakeInsiderQuery(FakeBuybackQuery):
    pass


class QueryCacheTests(unittest.TestCase):
    def test_buyback_uses_cached_result_without_query(self) -> None:
        cached_payload = {
            "items": [{"symbol": "00700.HK", "date": "2026-03-10", "amount": 1234.0}],
            "total": 1,
        }

        with patch.object(buyback_service, "get_json", return_value=cached_payload):
            items, total = buyback_service.list_buyback(GuardDb(), symbol="00700.HK")

        self.assertEqual(total, 1)
        self.assertEqual(items, [BuybackOut(symbol="00700.HK", date=date(2026, 3, 10), amount=1234.0)])

    def test_buyback_caches_db_query_result(self) -> None:
        item = BuybackOut(symbol="00700.HK", date=date(2026, 3, 10), amount=1234.0)
        db = DummyDb(FakeBuybackQuery([item], 1))

        with (
            patch.object(buyback_service, "get_json", return_value=None),
            patch.object(buyback_service, "set_json") as set_json_mock,
        ):
            items, total = buyback_service.list_buyback(db, symbol="00700.HK")

        self.assertEqual(total, 1)
        self.assertEqual(len(items), 1)
        set_json_mock.assert_called_once()
        payload = set_json_mock.call_args.args[1]
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["symbol"], "00700.HK")

    def test_insider_trade_uses_cached_result_without_query(self) -> None:
        cached_payload = {
            "items": [{"id": 1, "symbol": "600519.SH", "date": "2026-03-10", "type": "increase", "shares": 1000.0}],
            "total": 1,
        }

        with patch.object(insider_trade_service, "get_json", return_value=cached_payload):
            items, total = insider_trade_service.list_insider_trades(GuardDb(), symbol="600519.SH")

        self.assertEqual(total, 1)
        self.assertEqual(
            items,
            [InsiderTradeOut(id=1, symbol="600519.SH", date=date(2026, 3, 10), type="increase", shares=1000.0)],
        )

    def test_insider_trade_caches_db_query_result(self) -> None:
        item = InsiderTradeOut(id=1, symbol="600519.SH", date=date(2026, 3, 10), type="increase", shares=1000.0)
        db = DummyDb(FakeInsiderQuery([item], 1))

        with (
            patch.object(insider_trade_service, "get_json", return_value=None),
            patch.object(insider_trade_service, "set_json") as set_json_mock,
        ):
            items, total = insider_trade_service.list_insider_trades(db, symbol="600519.SH")

        self.assertEqual(total, 1)
        self.assertEqual(len(items), 1)
        set_json_mock.assert_called_once()
        payload = set_json_mock.call_args.args[1]
        self.assertEqual(payload["total"], 1)
        self.assertEqual(payload["items"][0]["symbol"], "600519.SH")


if __name__ == "__main__":
    unittest.main()
