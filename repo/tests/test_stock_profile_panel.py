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

from app.routers.stock import get_stock_profile_panel
from app.schemas.stock import StockProfilePanelOut


class StockProfilePanelRouteTests(unittest.TestCase):
    def test_route_delegates_to_profile_assembler(self) -> None:
        panel = StockProfilePanelOut(
            symbol="000001.SH",
            name="PingAn",
            market="A",
            sector="Financials",
            quote={"current": 10.2, "change": 0.1, "last_close": 10.1},
            quote_detail={"pe_ttm": 5.2, "lot_size": 100},
            pankou={"diff": 1000, "ratio": 0.12, "bids": [], "asks": []},
            risk={"symbol": "000001.SH", "max_drawdown": -0.12, "volatility": 0.24, "as_of": "2026-03-24", "cache_hit": True},
            fundamental={"symbol": "000001.SH", "score": 82.5, "summary": "steady", "updated_at": "2026-03-24T10:00:00"},
        )

        with patch("app.routers.stock.build_stock_profile_panel", return_value=panel) as build_mock:
            result = get_stock_profile_panel("000001.SH")

        context = build_mock.call_args.args[0]
        self.assertEqual(context.normalized_symbol, "000001.SH")
        self.assertEqual(result.symbol, "000001.SH")
        self.assertEqual(result.quote_detail.pe_ttm, 5.2)

    def test_route_returns_single_panel_payload(self) -> None:
        with patch(
            "app.services.profile_service.get_stock_profile_payload",
            return_value={
                "symbol": "000001.SH",
                "name": "PingAn",
                "market": "A",
                "sector": "Financials",
                "quote": {"current": 10.2, "change": 0.1, "last_close": 10.1},
                "quote_detail": {"pe_ttm": 5.2, "lot_size": 100},
                "pankou": {"diff": 1000, "ratio": 0.12, "bids": [], "asks": []},
            },
        ), patch(
            "app.services.profile_service.get_risk_snapshot",
            return_value={"max_drawdown": -0.12, "volatility": 0.24, "as_of": "2026-03-24", "cache_hit": True},
        ), patch(
            "app.services.profile_service.get_fundamental_score",
            return_value={"symbol": "000001.SH", "score": 82.5, "summary": "steady", "updated_at": "2026-03-24T10:00:00"},
        ):
            result = get_stock_profile_panel("000001.SH")

        self.assertEqual(result.symbol, "000001.SH")
        self.assertEqual(result.quote_detail.pe_ttm, 5.2)
        self.assertEqual(result.pankou.diff, 1000)
        self.assertEqual(result.risk.max_drawdown, -0.12)
        self.assertEqual(result.fundamental.score, 82.5)


if __name__ == "__main__":
    unittest.main()
