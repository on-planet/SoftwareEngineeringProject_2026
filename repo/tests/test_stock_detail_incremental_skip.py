from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import json
import shutil
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.jobs import stock_detail_job


class StockDetailIncrementalSkipTests(unittest.TestCase):
    def test_filter_symbols_for_refresh_skips_fresh_symbols(self) -> None:
        now = datetime.now()
        state_dir = ROOT / "state" / "test_stock_detail_incremental_skip"
        status_path = state_dir / "stock_detail_job_status.json"
        if state_dir.exists():
            shutil.rmtree(state_dir, ignore_errors=True)
        state_dir.mkdir(parents=True, exist_ok=True)
        try:
            status_path.write_text(
                json.dumps(
                    {
                        "updated_at": now.isoformat(timespec="seconds"),
                        "items": {
                            "000001.SZ": {
                                "snapshot_checked_at": now.isoformat(timespec="seconds"),
                                "snapshot_has_data": True,
                                "research_checked_at": now.isoformat(timespec="seconds"),
                                "research_count": 0,
                                "intraday_checked_at": now.isoformat(timespec="seconds"),
                                "intraday_period_count": 3,
                            }
                        },
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )

            with patch.object(stock_detail_job, "STATE_DIR", state_dir), patch.object(
                stock_detail_job, "STATUS_PATH", status_path
            ), patch.object(
                stock_detail_job,
                "list_stock_live_snapshot_meta",
                return_value=[{"symbol": "000001.SZ", "as_of": now}],
            ), patch.object(
                stock_detail_job,
                "list_stock_intraday_meta",
                return_value=[{"symbol": "000001.SZ", "latest_timestamp": now, "period_count": 3}],
            ):
                refresh_symbols, skipped = stock_detail_job._filter_symbols_for_refresh(["000001.SZ"])

            self.assertEqual(refresh_symbols, [])
            self.assertEqual(skipped, 1)
        finally:
            if state_dir.exists():
                shutil.rmtree(state_dir, ignore_errors=True)

    def test_filter_symbols_for_refresh_keeps_stale_symbols(self) -> None:
        stale = datetime.now() - timedelta(hours=stock_detail_job.SNAPSHOT_MAX_AGE_HOURS + 2)
        with patch.object(
            stock_detail_job,
            "list_stock_live_snapshot_meta",
            return_value=[{"symbol": "000001.SZ", "as_of": stale}],
        ), patch.object(
            stock_detail_job,
            "list_stock_intraday_meta",
            return_value=[{"symbol": "000001.SZ", "latest_timestamp": stale, "period_count": 3}],
        ), patch.object(stock_detail_job, "_load_status_map", return_value={}):
            refresh_symbols, skipped = stock_detail_job._filter_symbols_for_refresh(["000001.SZ"])

        self.assertEqual(refresh_symbols, ["000001.SZ"])
        self.assertEqual(skipped, 0)


if __name__ == "__main__":
    unittest.main()
