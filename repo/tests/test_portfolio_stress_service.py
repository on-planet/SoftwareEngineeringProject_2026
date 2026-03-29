from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import sys
import types
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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

from app.models.base import Base
from app.models.daily_prices import DailyPrice
from app.models.stocks import Stock
from app.models.user_bought_target import UserBoughtTarget
from app.schemas.portfolio_stress import PortfolioStressPreviewIn, PortfolioStressRuleIn
from app.services.portfolio_stress_service import (
    get_bought_target_stress_test,
    preview_custom_bought_target_stress_test,
)


class PortfolioStressServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            engine,
            tables=[
                UserBoughtTarget.__table__,
                Stock.__table__,
                DailyPrice.__table__,
            ],
        )
        session_factory = sessionmaker(bind=engine)
        self.db = session_factory()
        self.addCleanup(self.db.close)
        self._seed_rows()

    def _seed_rows(self) -> None:
        self.db.add_all(
            [
                Stock(symbol="000001.SZ", name="Ping An Bank", market="A", sector="Bank"),
                Stock(symbol="00700.HK", name="Tencent", market="HK", sector="Tech"),
                Stock(symbol="600048.SH", name="Poly Dev", market="A", sector="Real Estate"),
            ]
        )
        self.db.add_all(
            [
                UserBoughtTarget(
                    user_id=7,
                    symbol="000001.SZ",
                    buy_price=10.0,
                    lots=100.0,
                    buy_date=date(2026, 3, 1),
                    fee=0.0,
                    note="bank",
                    created_at=datetime(2026, 3, 1, 9, 0, 0),
                    updated_at=datetime(2026, 3, 1, 9, 0, 0),
                ),
                UserBoughtTarget(
                    user_id=7,
                    symbol="00700.HK",
                    buy_price=20.0,
                    lots=50.0,
                    buy_date=date(2026, 3, 1),
                    fee=0.0,
                    note="tech",
                    created_at=datetime(2026, 3, 1, 9, 0, 0),
                    updated_at=datetime(2026, 3, 1, 9, 0, 0),
                ),
                UserBoughtTarget(
                    user_id=7,
                    symbol="600048.SH",
                    buy_price=15.0,
                    lots=40.0,
                    buy_date=date(2026, 3, 1),
                    fee=0.0,
                    note="property",
                    created_at=datetime(2026, 3, 1, 9, 0, 0),
                    updated_at=datetime(2026, 3, 1, 9, 0, 0),
                ),
            ]
        )
        self.db.add_all(
            [
                DailyPrice(symbol="000001.SZ", date=date(2026, 3, 20), open=10.0, high=10.2, low=9.9, close=10.0, volume=1000),
                DailyPrice(symbol="00700.HK", date=date(2026, 3, 20), open=20.0, high=20.4, low=19.7, close=20.0, volume=1000),
                DailyPrice(symbol="600048.SH", date=date(2026, 3, 20), open=15.0, high=15.2, low=14.8, close=15.0, volume=1000),
            ]
        )
        self.db.commit()

    def test_returns_three_presets_and_correct_bank_loss(self) -> None:
        payload = get_bought_target_stress_test(self.db, 7, position_limit=5)

        self.assertEqual(payload.summary.holdings_count, 3)
        self.assertEqual(payload.summary.scenario_count, 3)
        bank_scenario = next(item for item in payload.scenarios if item.code == "bank_sector_drop")
        self.assertAlmostEqual(bank_scenario.loss_amount, 50.0, places=4)
        self.assertAlmostEqual(bank_scenario.impacted_weight, 1000.0 / 2600.0, places=4)
        self.assertEqual(bank_scenario.affected_positions[0].symbol, "000001.SZ")

    def test_yield_up_scenario_aggregates_sector_impacts(self) -> None:
        payload = get_bought_target_stress_test(self.db, 7, position_limit=5)

        scenario = next(item for item in payload.scenarios if item.code == "us_yield_up_50bp")
        self.assertGreater(scenario.loss_amount, 0.0)
        labels = {item.label for item in scenario.sector_impacts}
        self.assertIn("金融", labels)
        self.assertIn("科技", labels)
        self.assertIn("房地产", labels)

    def test_custom_preview_allows_stacked_rules(self) -> None:
        payload = preview_custom_bought_target_stress_test(
            self.db,
            7,
            PortfolioStressPreviewIn(
                name="custom stress",
                description="preview",
                position_limit=5,
                rules=[
                    PortfolioStressRuleIn(scope_type="market", scope_value="HK", shock_pct=-0.03),
                    PortfolioStressRuleIn(scope_type="sector", scope_value="Tech", shock_pct=-0.02),
                    PortfolioStressRuleIn(scope_type="symbol", scope_value="600048.SH", shock_pct=-0.01),
                ],
            ),
        )

        self.assertEqual(payload["code"], "custom_preview")
        affected = {item["symbol"]: item for item in payload["affected_positions"]}
        self.assertAlmostEqual(float(affected["00700.HK"]["shock_pct"]), -0.05, places=4)
        self.assertAlmostEqual(float(affected["600048.SH"]["shock_pct"]), -0.01, places=4)
        self.assertAlmostEqual(float(payload["loss_amount"]), 56.0, places=4)


if __name__ == "__main__":
    unittest.main()
