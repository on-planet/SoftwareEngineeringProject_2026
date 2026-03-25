from __future__ import annotations

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class LiveMarketServiceArchitectureTests(unittest.TestCase):
    def test_live_market_service_does_not_import_etl_modules_directly(self) -> None:
        source = (ROOT / "api" / "app" / "services" / "live_market_service.py").read_text(encoding="utf-8")

        self.assertNotIn("from etl.fetchers", source)
        self.assertNotIn("from etl.transformers", source)
        self.assertIn("from app.services.live_market_remote import", source)
        self.assertIn("from app.services.live_market_metrics import", source)
