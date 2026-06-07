from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

from app.services import live_market_remote
from etl.fetchers import akshare_market_client


class KlineIndexAdapterTests(unittest.TestCase):
    def test_remote_kline_forwards_index_flag_to_adapter(self) -> None:
        adapter = Mock()
        adapter.get_kline_history.return_value = []

        with patch.object(live_market_remote, "get_market_data_adapter", return_value=adapter):
            rows = live_market_remote.get_kline_history(
                "000001.SH",
                period="day",
                count=240,
                as_of=None,
                is_index=True,
            )

        self.assertEqual(rows, [])
        adapter.get_kline_history.assert_called_once_with(
            "000001.SH",
            period="day",
            count=240,
            as_of=None,
            is_index=True,
        )

    def test_index_kline_falls_back_to_eastmoney_payload(self) -> None:
        class FakeResponse:
            @staticmethod
            def raise_for_status() -> None:
                return None

            @staticmethod
            def json() -> dict:
                return {
                    "data": {
                        "klines": [
                            "2026-03-13,3000,3010,3020,2990,100000",
                            "2026-03-14,3010,3030,3040,3005,120000",
                        ]
                    }
                }

        class FakeSession:
            trust_env = True

            def get(self, *args, **kwargs):
                self.trust_env = False
                return FakeResponse()

        with patch.object(
            akshare_market_client.ak,
            "index_zh_a_hist",
            side_effect=ConnectionError("blocked"),
        ), patch.object(
            akshare_market_client.requests,
            "Session",
            return_value=FakeSession(),
        ):
            rows = akshare_market_client._get_index_kline_history(
                "000001.SH",
                period="day",
                count=10,
                as_of=None,
            )

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]["close"], 3030.0)
        self.assertEqual(rows[-1]["volume"], 120000.0)


if __name__ == "__main__":
    unittest.main()
