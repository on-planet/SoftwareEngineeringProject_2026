from __future__ import annotations

from pathlib import Path
import os
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from etl.fetchers import events_client, news_client, snowball_client


class HongKongEtlFallbackTests(unittest.TestCase):
    def test_news_symbols_fall_back_to_cached_hk_universe(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(news_client, "list_cached_symbols", return_value=["00700.HK", "00005.HK"]),
        ):
            self.assertEqual(news_client._rss_symbols(), ["00700.HK", "00005.HK"])

    def test_event_symbols_expand_with_cached_hk_universe(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(events_client, "list_cached_symbols", return_value=["00700.HK", "00005.HK"]),
        ):
            self.assertEqual(
                events_client._event_symbols(),
                ["600000.SH", "000001.SZ", "600519.SH", "00700.HK", "00005.HK"],
            )

    def test_buyback_symbols_fall_back_to_cached_hk_universe(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(events_client, "get_cache_string", return_value=""),
            patch.object(events_client, "list_cached_symbols", return_value=["00700.HK", "00005.HK"]),
        ):
            self.assertEqual(events_client._rsshub_hk_symbols(), ["00700.HK", "00005.HK"])

    def test_zero_only_financial_rows_are_treated_as_invalid(self) -> None:
        self.assertFalse(
            snowball_client._financial_row_has_signal(
                {
                    "revenue": 0.0,
                    "net_income": 0.0,
                    "cash_flow": 0.0,
                    "roe": 0.0,
                    "debt_ratio": 0.0,
                }
            )
        )
        self.assertTrue(
            snowball_client._financial_row_has_signal(
                {
                    "revenue": 0.0,
                    "net_income": 1.0,
                    "cash_flow": 0.0,
                    "roe": 0.0,
                    "debt_ratio": 0.0,
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
