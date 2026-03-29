from __future__ import annotations

from datetime import date
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

from app.routers.user_targets import (
    get_my_bought_target_stress_test,
    preview_my_bought_target_stress_test,
)
from app.schemas.portfolio_stress import PortfolioStressPreviewIn, PortfolioStressRuleIn


class UserTargetsRouteTests(unittest.TestCase):
    def test_stress_test_route_returns_service_payload(self) -> None:
        payload = {
            "summary": {
                "as_of": date(2026, 3, 20),
                "holdings_count": 3,
                "total_value": 2600.0,
                "scenario_count": 3,
                "worst_scenario_code": "hk_tech_pullback",
                "worst_scenario_name": "港股科技回撤",
                "worst_loss_amount": 80.0,
                "worst_loss_pct": 80.0 / 2600.0,
                "max_impacted_weight": 0.38,
            },
            "scenarios": [],
        }

        with patch("app.routers.user_targets.get_bought_target_stress_test", return_value=payload) as service_mock:
            result = get_my_bought_target_stress_test(
                position_limit=9,
                db=MagicMock(),
                current_user=SimpleNamespace(id=12),
            )

        self.assertEqual(result["summary"]["worst_scenario_code"], "hk_tech_pullback")
        service_mock.assert_called_once()
        args, kwargs = service_mock.call_args
        self.assertEqual(args[1], 12)
        self.assertEqual(kwargs["position_limit"], 9)

    def test_custom_preview_route_returns_service_payload(self) -> None:
        request_payload = PortfolioStressPreviewIn(
            name="custom",
            description="preview",
            position_limit=6,
            rules=[
                PortfolioStressRuleIn(scope_type="market", scope_value="HK", shock_pct=-0.08),
            ],
        )
        response_payload = {
            "code": "custom_preview",
            "name": "custom",
            "description": "preview",
            "rules": ["market:HK -8.0%"],
            "projected_value": 1000.0,
            "portfolio_change": -80.0,
            "portfolio_change_pct": -0.08,
            "loss_amount": 80.0,
            "loss_pct": 0.08,
            "impacted_value": 1000.0,
            "impacted_weight": 1.0,
            "average_shock_pct": -0.08,
            "affected_positions": [],
            "sector_impacts": [],
            "market_impacts": [],
        }

        with patch("app.routers.user_targets.preview_custom_bought_target_stress_test", return_value=response_payload) as service_mock:
            result = preview_my_bought_target_stress_test(
                request_payload,
                db=MagicMock(),
                current_user=SimpleNamespace(id=12),
            )

        self.assertEqual(result["code"], "custom_preview")
        service_mock.assert_called_once()
        args, _ = service_mock.call_args
        self.assertEqual(args[1], 12)
        self.assertEqual(args[2], request_payload)


if __name__ == "__main__":
    unittest.main()
