from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from app.schemas.portfolio_stress import PortfolioScenarioLabIn
from app.services.portfolio_scenario_lab_service import run_portfolio_scenario_lab


class PortfolioScenarioLabServiceTests(unittest.TestCase):
    def test_lab_passes_factor_overrides_to_custom_stress_evaluator(self) -> None:
        scenario_payload = {
            "code": "scenario_lab_preview",
            "name": "test",
            "description": "test",
            "rules": ["rule"],
            "projected_value": 1000.0,
            "portfolio_change": -20.0,
            "portfolio_change_pct": -0.02,
            "loss_amount": 20.0,
            "loss_pct": 0.02,
            "impacted_value": 500.0,
            "impacted_weight": 0.5,
            "average_shock_pct": -0.04,
            "affected_positions": [],
            "sector_impacts": [],
            "market_impacts": [],
        }
        with patch("app.services.portfolio_scenario_lab_service.evaluate_custom_bought_target_stress_scenario") as mocked:
            mocked.return_value = scenario_payload
            result = run_portfolio_scenario_lab(
                None,  # type: ignore[arg-type]
                7,
                PortfolioScenarioLabIn(text="油价上涨8%，人民币贬值，利率上行50bp", position_limit=8),
            )

        kwargs = mocked.call_args.kwargs
        factor_overrides = dict(kwargs.get("factor_overrides") or {})
        self.assertGreater(float(factor_overrides.get("commodity_shock") or 0.0), 0.0)
        self.assertGreater(float(factor_overrides.get("fx_shock") or 0.0), 0.0)
        self.assertGreater(float(factor_overrides.get("rate_shock") or 0.0), 0.0)
        self.assertIn("propagation_lambda", factor_overrides)
        self.assertEqual(result.scenario.code, "scenario_lab_preview")


if __name__ == "__main__":
    unittest.main()
