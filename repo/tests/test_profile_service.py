from __future__ import annotations

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

from app.services.profile_service import StockRequestContext, build_stock_profile_panel


class ProfileServiceTests(unittest.TestCase):
    def test_build_stock_profile_panel_reuses_request_context_cache(self) -> None:
        with patch(
            "app.services.profile_service.get_stock_profile_payload",
            return_value={
                "symbol": "000001.SH",
                "name": "PingAn",
                "market": "A",
                "sector": "Financials",
                "quote": {"current": 10.2},
            },
        ) as profile_mock, patch(
            "app.services.profile_service.get_risk_snapshot",
            return_value={"max_drawdown": -0.12, "volatility": 0.24, "as_of": "2026-03-24", "cache_hit": True},
        ) as risk_mock, patch(
            "app.services.profile_service.get_fundamental_score",
            return_value={"symbol": "000001.SH", "score": 82.5, "summary": "steady", "updated_at": "2026-03-24T10:00:00"},
        ) as fundamental_mock:
            context = StockRequestContext("000001.SH")
            first = build_stock_profile_panel(context)
            second = build_stock_profile_panel(context)

        self.assertIsNotNone(first)
        self.assertEqual(first.symbol, second.symbol)
        self.assertEqual(first.fundamental.score, 82.5)
        profile_mock.assert_called_once_with("000001.SH", prefer_live=False)
        risk_mock.assert_called_once_with("000001.SH", window=60)
        fundamental_mock.assert_called_once_with("000001.SH")

    def test_request_context_caches_research_and_kline_payloads(self) -> None:
        with patch(
            "app.services.profile_service.get_stock_research",
            return_value={"symbol": "000001.SH", "reports": [], "earning_forecasts": []},
        ) as research_mock, patch(
            "app.services.profile_service.get_stock_kline",
            return_value=[{"date": "2026-03-24", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0}],
        ) as kline_mock:
            context = StockRequestContext("000001.SH")
            context.get_research_payload(report_limit=10, forecast_limit=10)
            context.get_research_payload(report_limit=10, forecast_limit=10)
            context.get_stock_kline(period="day", limit=60)
            context.get_stock_kline(period="day", limit=60)

        research_mock.assert_called_once_with("000001.SH", report_limit=10, forecast_limit=10)
        kline_mock.assert_called_once_with("000001.SH", period="day", limit=60, end=None, start=None)


if __name__ == "__main__":
    unittest.main()
