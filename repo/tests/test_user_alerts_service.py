from __future__ import annotations

from datetime import date, datetime
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

from app.models.user_alert_rule import UserAlertRule
from app.services.user_alerts_service import get_alert_center


class AlertCenterServiceTests(unittest.TestCase):
    def test_get_alert_center_evaluates_price_event_and_earnings_rules(self) -> None:
        price_rule = UserAlertRule(
            id=1,
            user_id=7,
            name="平安银行突破",
            rule_type="price",
            symbol="000001.SZ",
            price_operator="gte",
            threshold=10.0,
            lookback_days=7,
            is_active=True,
            note="",
        )
        event_rule = UserAlertRule(
            id=2,
            user_id=7,
            name="腾讯回购提醒",
            rule_type="event",
            symbol="00700.HK",
            event_type="buyback",
            lookback_days=5,
            is_active=True,
            note="",
        )
        earnings_rule = UserAlertRule(
            id=3,
            user_id=7,
            name="宁德时代财报",
            rule_type="earnings",
            symbol="300750.SZ",
            research_kind="report",
            lookback_days=10,
            is_active=True,
            note="",
        )

        with patch(
            "app.services.user_alerts_service.list_alert_rules",
            return_value=[price_rule, event_rule, earnings_rule],
        ), patch(
            "app.services.user_alerts_service.get_stock_compare_batch",
            return_value=[
                {
                    "symbol": "000001.SZ",
                    "quote": {"current": 11.3},
                }
            ],
        ), patch(
            "app.services.user_alerts_service.list_event_timeline",
            return_value=([SimpleNamespace(date=date(2026, 3, 24), type="buyback", title="股份回购披露")], 1),
        ), patch(
            "app.services.user_alerts_service.get_stock_research",
            return_value={
                "reports": [
                    {
                        "title": "一季报点评",
                        "published_at": datetime(2026, 3, 24, 10, 0, 0),
                    }
                ],
                "earning_forecasts": [],
            },
        ):
            result = get_alert_center(MagicMock(), 7)

        self.assertEqual(result.total, 3)
        self.assertEqual(result.triggered, 3)
        self.assertTrue(all(item.triggered for item in result.items))
        self.assertIn("最新价", result.items[0].status_message)
        self.assertEqual(result.items[1].context_title, "股份回购披露")
        self.assertEqual(result.items[2].context_title, "一季报点评")


if __name__ == "__main__":
    unittest.main()
