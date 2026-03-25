from __future__ import annotations

from datetime import date, datetime, timedelta
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd
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
from app.models.buyback import Buyback
from app.models.daily_prices import DailyPrice
from app.models.events import Event
from app.models.financials import Financial
from app.models.stock_live_snapshot import StockLiveSnapshot
from app.models.stock_research_item import StockResearchItem
from app.models.stock_strategy_run import StockStrategyRun
from app.models.stock_strategy_score import StockStrategyScore
from app.models.stocks import Stock
from app.services import smoke_butt_strategy_service as service


class _FakePredictor:
    def __init__(self, *, label: str, path: str, problem_type: str, eval_metric: str) -> None:
        self.label = label
        self.path = path
        self.problem_type = problem_type
        self.eval_metric = eval_metric

    def fit(self, **kwargs):
        self.fit_kwargs = kwargs
        return self

    def predict(self, data):
        frame = pd.DataFrame(data)
        signal = frame.get("profit_quality", 0).fillna(0) - frame.get("ret_120d", 0).fillna(0)
        return pd.Series(signal.astype("float64"), index=frame.index)

    def leaderboard(self, data, silent: bool = True):
        _ = data
        _ = silent
        return pd.DataFrame(
            [
                {
                    "model": "FakeWeightedEnsemble",
                    "score_val": 0.21,
                    "fit_time": 1.4,
                    "pred_time_val": 0.02,
                }
            ]
        )

    def feature_importance(self, data, silent: bool = True):
        _ = data
        _ = silent
        return pd.DataFrame(
            {
                "importance": [0.48, 0.31],
                "stddev": [0.03, 0.02],
                "p_value": [0.05, 0.08],
                "n": [32, 32],
            },
            index=["profit_quality", "ret_120d"],
        )


class SmokeButtStrategyServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(
            engine,
            tables=[
                Stock.__table__,
                DailyPrice.__table__,
                Financial.__table__,
                Event.__table__,
                Buyback.__table__,
                StockResearchItem.__table__,
                StockLiveSnapshot.__table__,
                StockStrategyRun.__table__,
                StockStrategyScore.__table__,
            ],
        )
        session_factory = sessionmaker(bind=engine)
        self.db = session_factory()
        self.addCleanup(self.db.close)
        self._seed_rows()

    def _seed_rows(self) -> None:
        symbols = [
            ("000001.SZ", "Alpha", "A", "Bank"),
            ("000002.SZ", "Beta", "A", "RealEstate"),
            ("00700.HK", "Tencent", "HK", "Tech"),
            ("09988.HK", "Alibaba", "HK", "Tech"),
        ]
        start = date(2025, 7, 1)
        days = 260
        for symbol, name, market, sector in symbols:
            self.db.add(Stock(symbol=symbol, name=name, market=market, sector=sector))
            for idx in range(days):
                current_date = start + timedelta(days=idx)
                trend = {
                    "000001.SZ": -0.012,
                    "000002.SZ": -0.006,
                    "00700.HK": 0.004,
                    "09988.HK": -0.018,
                }[symbol]
                close = 20 + (idx * trend) + (0.8 if market == "HK" else 0.0)
                self.db.add(
                    DailyPrice(
                        symbol=symbol,
                        date=current_date,
                        open=close * 0.99,
                        high=close * 1.02,
                        low=close * 0.98,
                        close=close,
                        volume=1000000 + (idx * 1500),
                    )
                )
            self.db.add(StockLiveSnapshot(symbol=symbol, pb=0.9, pe_ttm=8.5, dividend_yield=5.417, market_cap=1_000_000_000))
            for period, revenue, net_income, cash_flow, roe, debt_ratio in [
                ("202503", 120.0, 18.0, 26.0, 0.12, 0.42),
                ("202506", 126.0, 19.0, 28.0, 0.13, 0.41),
                ("202509", 135.0, 20.0, 31.0, 0.15, 0.40),
                ("202512", 140.0, 22.0, 34.0, 0.16, 0.39),
            ]:
                self.db.add(
                    Financial(
                        symbol=symbol,
                        period=period,
                        revenue=revenue,
                        net_income=net_income,
                        cash_flow=cash_flow,
                        roe=roe,
                        debt_ratio=debt_ratio,
                    )
                )
            self.db.add(Event(symbol=symbol, type="announcement", title="event", date=date(2026, 2, 1)))
            self.db.add(Buyback(symbol=symbol, date=date(2026, 1, 15), amount=12_000_000))
            self.db.add(
                StockResearchItem(
                    symbol=symbol,
                    item_type="report",
                    title=f"{symbol}-report",
                    published_at=datetime(2026, 2, 10, 9, 30, 0),
                    link="https://example.com/report",
                    summary="steady",
                    institution="Broker",
                    rating="buy",
                    source="unit-test",
                )
            )
        self.db.commit()

    def test_train_strategy_persists_run_and_scores(self) -> None:
        with patch.object(service, "_load_tabular_predictor", return_value=_FakePredictor), patch.object(
            service, "MIN_TRAIN_ROWS", 4
        ):
            run, items = service.train_smoke_butt_strategy(
                self.db,
                as_of=date(2026, 3, 15),
                sample_step=20,
                time_limit_seconds=30,
                force_retrain=True,
            )

        self.assertEqual(run["strategy_code"], service.STRATEGY_CODE)
        self.assertEqual(self.db.query(StockStrategyRun).count(), 1)
        self.assertEqual(self.db.query(StockStrategyScore).count(), 4)
        self.assertEqual(items[0]["rank"], 1)
        self.assertEqual(items[0]["symbol"], "09988.HK")
        self.assertEqual(items[0]["signal"], "strong_buy")

    def test_train_strategy_reuses_existing_run_when_not_forced(self) -> None:
        with patch.object(service, "_load_tabular_predictor", return_value=_FakePredictor), patch.object(
            service, "MIN_TRAIN_ROWS", 4
        ):
            first_run, _ = service.train_smoke_butt_strategy(
                self.db,
                as_of=date(2026, 3, 15),
                sample_step=20,
                time_limit_seconds=30,
                force_retrain=True,
            )

        with patch.object(service, "_load_tabular_predictor", side_effect=AssertionError("unexpected retrain")):
            second_run, items = service.train_smoke_butt_strategy(
                self.db,
                as_of=date(2026, 3, 15),
                sample_step=20,
                time_limit_seconds=30,
                force_retrain=False,
            )

        self.assertEqual(first_run["id"], second_run["id"])
        self.assertEqual(len(items), 4)
        self.assertEqual(self.db.query(StockStrategyRun).count(), 1)

    def test_list_and_detail_return_latest_scores(self) -> None:
        with patch.object(service, "_load_tabular_predictor", return_value=_FakePredictor), patch.object(
            service, "MIN_TRAIN_ROWS", 4
        ):
            service.train_smoke_butt_strategy(
                self.db,
                as_of=date(2026, 3, 15),
                sample_step=20,
                time_limit_seconds=30,
                force_retrain=True,
            )

        items, total, run = service.list_smoke_butt_candidates(self.db, market="HK", limit=10, offset=0)
        detail = service.get_smoke_butt_detail(self.db, "09988.HK")

        self.assertEqual(total, 2)
        self.assertIsNotNone(run)
        self.assertEqual(items[0]["market"], "HK")
        self.assertIsNotNone(detail)
        self.assertEqual(detail["symbol"], "09988.HK")
        self.assertTrue(detail["drivers"])
        self.assertTrue(detail["feature_values"])
        dividend_driver = next(
            item for item in detail["drivers"] if item["label"] == "\u80a1\u606f\u7387\u8f83\u9ad8"
        )
        dividend_feature = next(
            item for item in detail["feature_values"] if item["name"] == "\u80a1\u606f\u7387"
        )
        self.assertAlmostEqual(dividend_driver["value"], 0.05417, places=5)
        self.assertEqual(dividend_driver["display_value"], "5.42%")
        self.assertAlmostEqual(dividend_feature["value"], 0.05417, places=5)
        self.assertEqual(dividend_feature["display_value"], "5.42%")

    def test_detail_normalizes_legacy_dividend_payloads(self) -> None:
        run = StockStrategyRun(
            strategy_code=service.STRATEGY_CODE,
            strategy_name=service.STRATEGY_NAME,
            as_of=date(2026, 3, 20),
            label_horizon=service.DEFAULT_HORIZON_DAYS,
            status="ready",
        )
        self.db.add(run)
        self.db.flush()
        self.db.add(
            StockStrategyScore(
                run_id=run.id,
                symbol="000001.SZ",
                as_of=run.as_of,
                score=72.0,
                rank=1,
                percentile=0.95,
                expected_return=0.12,
                signal="buy",
                summary="legacy",
                driver_factors_json=json.dumps(
                    [
                        {
                            "label": "\u80a1\u606f\u7387\u8f83\u9ad8",
                            "tone": "positive",
                            "value": 5.417,
                            "display_value": "541.70%",
                        }
                    ],
                    ensure_ascii=False,
                ),
                feature_values_json=json.dumps(
                    [
                        {
                            "name": "\u80a1\u606f\u7387",
                            "value": 5.417,
                            "display_value": "541.70%",
                        }
                    ],
                    ensure_ascii=False,
                ),
            )
        )
        self.db.commit()

        detail = service.get_smoke_butt_detail(self.db, "000001.SZ")

        self.assertIsNotNone(detail)
        self.assertAlmostEqual(detail["drivers"][0]["value"], 0.05417, places=5)
        self.assertEqual(detail["drivers"][0]["display_value"], "5.42%")
        self.assertAlmostEqual(detail["feature_values"][0]["value"], 0.05417, places=5)
        self.assertEqual(detail["feature_values"][0]["display_value"], "5.42%")


if __name__ == "__main__":
    unittest.main()
