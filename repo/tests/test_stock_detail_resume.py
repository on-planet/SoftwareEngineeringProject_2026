from __future__ import annotations

from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.jobs import stock_detail_job


class StockDetailResumeTests(unittest.TestCase):
    def test_run_stock_detail_job_resumes_from_checkpoint(self) -> None:
        target_symbols = ["000001.SZ", "000002.SZ", "000003.SZ", "000004.SZ", "000005.SZ"]
        flush_calls: list[int] = []
        collected_first: list[str] = []
        collected_second: list[str] = []

        def fake_collect_first(symbol: str, *, report_limit: int, forecast_limit: int) -> dict:
            collected_first.append(symbol)
            return {
                "symbol": symbol,
                "snapshot": {"symbol": symbol, "as_of": "2026-03-16T00:00:00"},
                "research": [{"symbol": symbol, "item_type": "report", "title": symbol}],
                "intraday": [{"symbol": symbol, "period": "1m", "timestamp": 1}],
            }

        def fake_collect_second(symbol: str, *, report_limit: int, forecast_limit: int) -> dict:
            collected_second.append(symbol)
            return {
                "symbol": symbol,
                "snapshot": {"symbol": symbol, "as_of": "2026-03-16T00:00:00"},
                "research": [{"symbol": symbol, "item_type": "report", "title": symbol}],
                "intraday": [{"symbol": symbol, "period": "1m", "timestamp": 1}],
            }

        state_dir = ROOT / "state" / "test_stock_detail_resume"
        checkpoint_path = state_dir / "stock_detail_job_checkpoint.json"
        if state_dir.exists():
            shutil.rmtree(state_dir, ignore_errors=True)
        state_dir.mkdir(parents=True, exist_ok=True)
        try:

            def fake_flush_first(snapshot_rows: list[dict], research_rows: list[dict], intraday_rows: list[dict]) -> tuple[int, int, int]:
                flush_calls.append(len(snapshot_rows))
                if len(flush_calls) == 2:
                    raise KeyboardInterrupt("stop after first committed batch")
                return len(snapshot_rows), len(research_rows), len(intraday_rows)

            with patch.object(stock_detail_job, "STATE_DIR", state_dir), patch.object(
                stock_detail_job, "CHECKPOINT_PATH", checkpoint_path
            ), patch.object(stock_detail_job, "_target_symbols", return_value=target_symbols), patch.object(
                stock_detail_job, "_filter_symbols_for_refresh", return_value=(target_symbols, 0)
            ), patch.object(
                stock_detail_job, "_collect_symbol_payload", side_effect=fake_collect_first
            ), patch.object(stock_detail_job, "_flush_batch_rows", side_effect=fake_flush_first), patch.dict(
                "os.environ",
                {"STOCK_DETAIL_JOB_BATCH_SIZE": "2", "STOCK_DETAIL_JOB_PROGRESS_EVERY": "1"},
                clear=False,
            ):
                with self.assertRaises(KeyboardInterrupt):
                    stock_detail_job.run_stock_detail_job()

            self.assertTrue(checkpoint_path.exists())
            with patch.object(stock_detail_job, "CHECKPOINT_PATH", checkpoint_path):
                self.assertEqual(
                    stock_detail_job._load_checkpoint(
                        stock_detail_job._checkpoint_signature(target_symbols, report_limit=10, forecast_limit=10)
                    ),
                    2,
                )
            self.assertEqual(collected_first[:2], ["000001.SZ", "000002.SZ"])

            with patch.object(stock_detail_job, "STATE_DIR", state_dir), patch.object(
                stock_detail_job, "CHECKPOINT_PATH", checkpoint_path
            ), patch.object(stock_detail_job, "_target_symbols", return_value=target_symbols), patch.object(
                stock_detail_job, "_filter_symbols_for_refresh", return_value=(target_symbols, 0)
            ), patch.object(
                stock_detail_job, "_collect_symbol_payload", side_effect=fake_collect_second
            ), patch.object(stock_detail_job, "_flush_batch_rows", side_effect=lambda s, r, i: (len(s), len(r), len(i))), patch.dict(
                "os.environ",
                {"STOCK_DETAIL_JOB_BATCH_SIZE": "2", "STOCK_DETAIL_JOB_PROGRESS_EVERY": "1"},
                clear=False,
            ):
                snapshot_count, research_count = stock_detail_job.run_stock_detail_job()

            self.assertEqual(snapshot_count, 3)
            self.assertEqual(research_count, 3)
            self.assertEqual(collected_second, ["000003.SZ", "000004.SZ", "000005.SZ"])
            self.assertFalse(checkpoint_path.exists())
        finally:
            if state_dir.exists():
                shutil.rmtree(state_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
