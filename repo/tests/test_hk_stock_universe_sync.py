from __future__ import annotations

import json
from pathlib import Path
import shutil
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.fetchers import akshare_hk_stock_client, market_client


class HKStockUniverseSyncTests(unittest.TestCase):
    def test_fetch_eastmoney_paginated_frame_uses_expanded_page_size(self) -> None:
        payloads = [
            {
                "data": {
                    "total": 3,
                    "diff": [
                        {"f12": "5", "f14": "HSBC"},
                        {"f12": "700", "f14": "Tencent"},
                    ],
                }
            },
            {
                "data": {
                    "total": 3,
                    "diff": [
                        {"f12": "941", "f14": "China Mobile"},
                    ],
                }
            },
        ]
        request_calls: list[tuple[str, str, dict]] = []

        def fake_request(function_name: str, url: str, params: dict) -> dict:
            request_calls.append((function_name, url, dict(params)))
            return payloads[len(request_calls) - 1]

        with patch.object(
            akshare_hk_stock_client,
            "_request_eastmoney_page_json",
            side_effect=fake_request,
        ), patch.object(
            akshare_hk_stock_client,
            "AKSHARE_HK_PAGE_DELAY_SECONDS",
            0.0,
        ):
            frame = akshare_hk_stock_client._fetch_eastmoney_paginated_frame("stock_hk_spot_em")

        self.assertEqual(frame.to_dict(orient="records"), [{"代码": "5", "名称": "HSBC"}, {"代码": "700", "名称": "Tencent"}, {"代码": "941", "名称": "China Mobile"}])
        self.assertEqual(request_calls[0][0], "stock_hk_spot_em")
        self.assertEqual(request_calls[0][2]["pz"], str(akshare_hk_stock_client.AKSHARE_HK_PAGE_SIZE))
        self.assertEqual(request_calls[1][2]["pn"], "2")

    def test_fetch_eastmoney_paginated_frame_tolerates_single_page_failure(self) -> None:
        payloads_by_page = {
            "1": {
                "data": {
                    "total": 6,
                    "diff": [
                        {"f12": "5", "f14": "HSBC"},
                        {"f12": "700", "f14": "Tencent"},
                    ],
                }
            },
            "3": {
                "data": {
                    "total": 6,
                    "diff": [
                        {"f12": "941", "f14": "China Mobile"},
                    ],
                }
            },
        }

        def fake_request(function_name: str, url: str, params: dict) -> dict:
            if params.get("pn") == "2":
                raise RuntimeError("connection aborted on page 2")
            return payloads_by_page[str(params.get("pn"))]

        with patch.object(
            akshare_hk_stock_client,
            "_request_eastmoney_page_json",
            side_effect=fake_request,
        ), patch.object(
            akshare_hk_stock_client,
            "AKSHARE_HK_PAGE_DELAY_SECONDS",
            0.0,
        ), patch.object(
            akshare_hk_stock_client,
            "AKSHARE_HK_PAGE_MAX_FAILED_PAGES",
            3,
        ):
            frame = akshare_hk_stock_client._fetch_eastmoney_paginated_frame("stock_hk_spot_em")

        self.assertEqual(
            frame.to_dict(orient="records"),
            [
                {"代码": "5", "名称": "HSBC"},
                {"代码": "700", "名称": "Tencent"},
                {"代码": "941", "名称": "China Mobile"},
            ],
        )

    def test_call_provider_function_falls_back_to_akshare_function(self) -> None:
        fallback_frame = pd.DataFrame([{"code": "5", "name": "HSBC"}])
        fake_ak = SimpleNamespace(stock_hk_spot_em=lambda: fallback_frame)

        with patch.object(
            akshare_hk_stock_client,
            "_fetch_eastmoney_paginated_frame",
            side_effect=RuntimeError("network boom"),
        ), patch.object(akshare_hk_stock_client, "ak", fake_ak):
            frame = akshare_hk_stock_client._call_provider_function("stock_hk_spot_em")

        self.assertIs(frame, fallback_frame)

    def test_fetch_hk_stock_universe_rows_normalizes_symbols(self) -> None:
        frame = pd.DataFrame(
            [
                {"code": "5", "name": "HSBC", "industry": "Bank"},
                {"code": "700", "name": "Tencent", "industry": "Tech"},
                {"code": "00005", "name": "HSBC", "industry": "Bank"},
            ]
        )
        with patch.object(
            akshare_hk_stock_client,
            "_call_provider_function",
            side_effect=[frame, None, None],
        ):
            rows = akshare_hk_stock_client.fetch_hk_stock_universe_rows()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["symbol"], "00005.HK")
        self.assertEqual(rows[0]["name"], "HSBC")
        self.assertEqual(rows[1]["symbol"], "00700.HK")
        self.assertEqual(rows[1]["sector"], "科技")

    def test_fetch_hk_stock_profile_rows_uses_comcnname_and_mbu(self) -> None:
        detail_frame = pd.DataFrame(
            [
                {"item": "comcnname", "value": "东方甄选"},
                {"item": "mbu", "value": "互联网服务"},
            ]
        )
        fake_ak = SimpleNamespace(stock_individual_basic_info_hk_xq=lambda symbol: detail_frame)
        with patch.object(akshare_hk_stock_client, "ak", fake_ak), patch.object(
            akshare_hk_stock_client,
            "AKSHARE_HK_DETAIL_DELAY_SECONDS",
            0.0,
        ):
            rows = akshare_hk_stock_client.fetch_hk_stock_profile_rows(["02097.HK"])

        self.assertEqual(rows, [{"symbol": "02097.HK", "name": "东方甄选", "market": "HK", "sector": "科技"}])

    def test_sync_hk_stock_universe_persists_rows(self) -> None:
        hk_rows = [
            {"symbol": "00005.HK", "name": "HSBC", "market": "HK", "sector": "Bank"},
            {"symbol": "00700.HK", "name": "Tencent", "market": "HK", "sector": "Tech"},
        ]
        state_dir = ROOT / "state" / "test_hk_stock_universe_persist_rows"
        checkpoint_path = state_dir / "hk_stock_universe_sync_checkpoint.json"
        if state_dir.exists():
            shutil.rmtree(state_dir, ignore_errors=True)
        state_dir.mkdir(parents=True, exist_ok=True)
        try:
            with patch.object(market_client, "STATE_DIR", state_dir), patch.object(
                market_client, "HK_UNIVERSE_CHECKPOINT_PATH", checkpoint_path
            ), patch.object(
                market_client, "fetch_hk_stock_universe_rows", return_value=hk_rows
            ), patch.object(
                market_client, "fetch_hk_stock_profile_rows", return_value=[]
            ), patch.object(
                market_client, "upsert_stocks"
            ) as upsert_mock, patch.object(market_client, "save_stock_basics_cache") as save_mock:
                count = market_client.sync_hk_stock_universe(force=True)
        finally:
            if state_dir.exists():
                shutil.rmtree(state_dir, ignore_errors=True)

        self.assertEqual(count, 2)
        upsert_mock.assert_called_once_with(hk_rows)
        save_mock.assert_called_once_with(hk_rows, merge=True)

    def test_sync_hk_stock_universe_resumes_from_checkpoint(self) -> None:
        hk_rows = [
            {"symbol": "00005.HK", "name": "HSBC", "market": "HK", "sector": "Bank"},
            {"symbol": "00700.HK", "name": "Tencent", "market": "HK", "sector": "Tech"},
            {"symbol": "00941.HK", "name": "China Mobile", "market": "HK", "sector": "Telecom"},
        ]
        state_dir = ROOT / "state" / "test_hk_stock_universe_sync"
        checkpoint_path = state_dir / "hk_stock_universe_sync_checkpoint.json"
        if state_dir.exists():
            shutil.rmtree(state_dir, ignore_errors=True)
        state_dir.mkdir(parents=True, exist_ok=True)
        first_batches: list[list[str]] = []
        second_batches: list[list[str]] = []
        try:

            def interrupting_upsert(rows: list[dict]) -> None:
                first_batches.append([str(item["symbol"]) for item in rows])
                if len(first_batches) == 2:
                    raise KeyboardInterrupt("stop after first persisted batch")

            with patch.object(market_client, "STATE_DIR", state_dir), patch.object(
                market_client, "HK_UNIVERSE_CHECKPOINT_PATH", checkpoint_path
            ), patch.object(
                market_client, "HK_UNIVERSE_SYNC_BATCH_SIZE", 2
            ), patch.object(
                market_client, "fetch_hk_stock_universe_rows", return_value=hk_rows
            ), patch.object(
                market_client, "fetch_hk_stock_profile_rows", return_value=[]
            ), patch.object(
                market_client, "upsert_stocks", side_effect=interrupting_upsert
            ), patch.object(
                market_client, "save_stock_basics_cache"
            ):
                with self.assertRaises(KeyboardInterrupt):
                    market_client.sync_hk_stock_universe(force=True)

            self.assertEqual(first_batches[0], ["00005.HK", "00700.HK"])
            self.assertTrue(checkpoint_path.exists())
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            self.assertEqual(checkpoint["next_index"], 2)

            with patch.object(market_client, "STATE_DIR", state_dir), patch.object(
                market_client, "HK_UNIVERSE_CHECKPOINT_PATH", checkpoint_path
            ), patch.object(
                market_client, "HK_UNIVERSE_SYNC_BATCH_SIZE", 2
            ), patch.object(
                market_client, "fetch_hk_stock_universe_rows"
            ) as fetch_mock, patch.object(
                market_client, "fetch_hk_stock_profile_rows", return_value=[]
            ), patch.object(
                market_client,
                "upsert_stocks",
                side_effect=lambda rows: second_batches.append([str(item["symbol"]) for item in rows]),
            ), patch.object(
                market_client, "save_stock_basics_cache"
            ):
                count = market_client.sync_hk_stock_universe(force=True)

            fetch_mock.assert_not_called()
            self.assertEqual(count, 3)
            self.assertEqual(second_batches, [["00941.HK"]])
            self.assertFalse(checkpoint_path.exists())
        finally:
            if state_dir.exists():
                shutil.rmtree(state_dir, ignore_errors=True)

    def test_get_stock_basic_auto_syncs_hk_universe_when_cache_is_incomplete(self) -> None:
        initial_rows = [
            {"symbol": "000001.SZ", "name": "Ping An Bank", "market": "A", "sector": "Bank"},
        ]
        refreshed_rows = initial_rows + [
            {"symbol": "00005.HK", "name": "HSBC", "market": "HK", "sector": "Bank"},
            {"symbol": "00700.HK", "name": "Tencent", "market": "HK", "sector": "Tech"},
        ]
        with patch.object(
            market_client,
            "load_stock_basics_cache",
            side_effect=[initial_rows, refreshed_rows],
        ), patch.object(
            market_client,
            "sync_hk_stock_universe",
            return_value=2,
        ) as sync_mock, patch.object(
            market_client,
            "load_baostock_industry_cache",
            return_value=[],
        ), patch.object(
            market_client,
            "save_stock_basics_cache",
        ):
            rows = market_client.get_stock_basic(force_refresh=False, allow_stale_cache=True)

        sync_mock.assert_called_once_with(force=False)
        self.assertEqual(len(rows), 3)
        self.assertEqual(sum(1 for row in rows if row["market"] == "HK"), 2)

    def test_get_stock_basic_does_not_auto_sync_hk_universe_for_requested_symbol_by_default(self) -> None:
        requested = ["00020.HK"]
        cached_rows: list[dict] = []
        snowball_rows = [{"symbol": "00020.HK", "name": "00020.HK", "market": "HK", "sector": "Unknown"}]
        with patch.object(
            market_client,
            "HK_UNIVERSE_SYNC_ON_REQUEST",
            False,
        ), patch.object(
            market_client,
            "load_stock_basics_cache",
            return_value=cached_rows,
        ), patch.object(
            market_client,
            "list_stock_rows",
            return_value=[],
        ), patch.object(
            market_client,
            "sb_get_stock_basics",
            return_value=snowball_rows,
        ), patch.object(
            market_client,
            "load_baostock_industry_cache",
            return_value=[],
        ), patch.object(
            market_client,
            "save_stock_basics_cache",
        ), patch.object(
            market_client,
            "sync_hk_stock_universe",
        ) as sync_mock:
            rows = market_client.get_stock_basic(requested, force_refresh=True, allow_stale_cache=False)

        sync_mock.assert_not_called()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "00020.HK")

    def test_get_stock_basic_requested_symbol_skips_hk_profile_enrichment_by_default(self) -> None:
        requested = ["00020.HK"]
        snowball_rows = [{"symbol": "00020.HK", "name": "00020.HK", "market": "HK", "sector": "Unknown"}]
        with patch.object(
            market_client,
            "HK_PROFILE_ENRICH_ON_REQUEST",
            False,
        ), patch.object(
            market_client,
            "load_stock_basics_cache",
            return_value=[],
        ), patch.object(
            market_client,
            "list_stock_rows",
            return_value=[],
        ), patch.object(
            market_client,
            "sb_get_stock_basics",
            return_value=snowball_rows,
        ), patch.object(
            market_client,
            "_enrich_hk_rows_with_akshare",
        ) as enrich_mock, patch.object(
            market_client,
            "load_baostock_industry_cache",
            return_value=[],
        ), patch.object(
            market_client,
            "save_stock_basics_cache",
        ):
            rows = market_client.get_stock_basic(requested, force_refresh=True, allow_stale_cache=False)

        enrich_mock.assert_not_called()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "00020.HK")


if __name__ == "__main__":
    unittest.main()
