from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from app.schemas.kline import KlinePoint
from app.services.live_market_metrics import (
    build_fundamental_payload,
    build_indicator_payload,
    build_risk_series,
    build_risk_snapshot_payload,
)


class LiveMarketMetricsTests(unittest.TestCase):
    def test_build_fundamental_payload_uses_latest_rows(self) -> None:
        rows = [
            {
                "period": "2025Q4",
                "revenue": 100.0,
                "net_income": 20.0,
                "cash_flow": 24.0,
                "debt_ratio": 0.45,
            },
            {
                "period": "2025Q3",
                "revenue": 80.0,
                "net_income": 16.0,
                "cash_flow": 18.0,
                "debt_ratio": 0.40,
            },
        ]

        payload = build_fundamental_payload("000001.SZ", rows, as_of=datetime(2026, 3, 24, 10, 0, 0))

        self.assertEqual(payload["symbol"], "000001.SZ")
        self.assertGreater(payload["score"], 0.0)
        self.assertIn("综合得分", payload["summary"])
        self.assertEqual(payload["updated_at"], datetime(2026, 3, 24, 10, 0, 0))

    def test_build_indicator_payload_supports_wr_series(self) -> None:
        rows = [
            {"date": date(2026, 3, 20), "high": 10.2, "low": 9.8, "close": 10.0, "volume": 1000.0},
            {"date": date(2026, 3, 21), "high": 10.5, "low": 9.9, "close": 10.3, "volume": 1200.0},
            {"date": date(2026, 3, 22), "high": 10.7, "low": 10.1, "close": 10.6, "volume": 1300.0},
        ]

        lines, params, payload = build_indicator_payload("wr", rows, 2)

        self.assertEqual(lines, ["wr"])
        self.assertEqual(params["window"], 2)
        self.assertEqual(len(payload["wr"]), 3)

    def test_build_risk_payloads_derive_snapshot_and_series(self) -> None:
        points = [
            KlinePoint(date=date(2026, 3, 20), open=10.0, high=10.1, low=9.8, close=10.0, volume=1000.0),
            KlinePoint(date=date(2026, 3, 21), open=10.1, high=10.4, low=10.0, close=10.3, volume=1200.0),
            KlinePoint(date=date(2026, 3, 22), open=10.4, high=10.7, low=10.2, close=10.5, volume=1300.0),
        ]

        snapshot = build_risk_snapshot_payload("000001.SZ", points)
        series = build_risk_series(points, window=2)

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["symbol"], "000001.SZ")
        self.assertEqual(snapshot["as_of"], date(2026, 3, 22))
        self.assertEqual(len(series), 3)
        self.assertEqual(series[-1].date, date(2026, 3, 22))
