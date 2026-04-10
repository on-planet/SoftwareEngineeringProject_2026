from __future__ import annotations

from datetime import date, datetime, timedelta
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
from app.models.stock_factor_exposure_cache import StockFactorExposureCache
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

    def test_factor_model_propagates_symbol_shock_to_correlated_holdings(self) -> None:
        self.db.query(DailyPrice).delete()
        start = date(2025, 12, 1)
        close_1 = 10.0
        close_2 = 20.0
        close_3 = 15.0
        rows: list[DailyPrice] = []
        for idx in range(95):
            item_date = start + timedelta(days=idx)
            r1 = 0.0015 + ((idx % 7) - 3) * 0.00018
            r2 = 0.0012 + ((idx % 7) - 3) * 0.00016
            r3 = 0.0004 + ((idx % 5) - 2) * 0.00008
            close_1 *= (1.0 + r1)
            close_2 *= (1.0 + r2)
            close_3 *= (1.0 + r3)
            rows.extend(
                [
                    DailyPrice(symbol="000001.SZ", date=item_date, open=close_1, high=close_1, low=close_1, close=close_1, volume=1000),
                    DailyPrice(symbol="00700.HK", date=item_date, open=close_2, high=close_2, low=close_2, close=close_2, volume=1000),
                    DailyPrice(symbol="600048.SH", date=item_date, open=close_3, high=close_3, low=close_3, close=close_3, volume=1000),
                ]
            )
        self.db.add_all(rows)
        self.db.commit()

        payload = preview_custom_bought_target_stress_test(
            self.db,
            7,
            PortfolioStressPreviewIn(
                name="factor propagation",
                description="symbol shock should spill over",
                position_limit=5,
                rules=[
                    PortfolioStressRuleIn(scope_type="symbol", scope_value="000001.SZ", shock_pct=-0.10),
                ],
            ),
        )

        self.assertTrue(any("传播后冲击" in str(item) for item in payload.get("rules", [])))
        affected = {item["symbol"]: item for item in payload.get("affected_positions", [])}
        self.assertIn("000001.SZ", affected)
        self.assertIn("00700.HK", affected)
        self.assertLess(float(affected["00700.HK"]["shock_pct"]), 0.0)
        self.assertGreater(self.db.query(StockFactorExposureCache).count(), 0)


if __name__ == "__main__":
    unittest.main()
