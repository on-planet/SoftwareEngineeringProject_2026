from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

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

from app.routers.strategy import (
    get_smoke_butt_strategy,
    list_smoke_butt_strategy,
    train_smoke_butt_strategy_route,
)
from app.schemas.strategy import SmokeButtTrainIn
from app.services.smoke_butt_strategy_service import AutoGluonUnavailableError


class StrategyRouteTests(unittest.TestCase):
    def test_list_route_wraps_page_payload(self) -> None:
        payload = (
            [
                {
                    "symbol": "09988.HK",
                    "name": "Alibaba",
                    "market": "HK",
                    "sector": "Tech",
                    "as_of": date(2026, 3, 15),
                    "score": 99.0,
                    "rank": 1,
                    "percentile": 1.0,
                    "expected_return": 0.18,
                    "signal": "strong_buy",
                    "summary": "top candidate",
                }
            ],
            1,
            {
                "id": 8,
                "strategy_code": "smoke_butt_autogluon",
                "strategy_name": "AutoGluon Smoke Butt",
                "as_of": date(2026, 3, 15),
                "label_horizon": 60,
                "status": "ready",
                "model_path": "etl/state/autogluon/run",
                "train_rows": 88,
                "scored_rows": 4,
                "trained_at": datetime(2026, 3, 15, 10, 0, 0),
                "evaluation": {"mae": 0.12},
                "leaderboard": [],
                "feature_importance": [],
            },
        )

        with patch("app.routers.strategy.list_smoke_butt_candidates", return_value=payload):
            result = list_smoke_butt_strategy(market="HK", signal=None, paging={"limit": 20, "offset": 0}, db=MagicMock())

        self.assertEqual(result["total"], 1)
        self.assertEqual(result["run"]["id"], 8)
        self.assertEqual(result["items"][0]["symbol"], "09988.HK")

    def test_detail_route_returns_nullable_payload(self) -> None:
        with patch("app.routers.strategy.get_smoke_butt_detail", return_value=None):
            result = get_smoke_butt_strategy("09988.HK", db=MagicMock())

        self.assertIsNone(result)

    def test_train_route_maps_dependency_error_to_503(self) -> None:
        with patch("app.routers.strategy.train_smoke_butt_strategy", side_effect=AutoGluonUnavailableError("missing")):
            with self.assertRaises(HTTPException) as exc_info:
                train_smoke_butt_strategy_route(SmokeButtTrainIn(), db=MagicMock())

        self.assertEqual(exc_info.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
