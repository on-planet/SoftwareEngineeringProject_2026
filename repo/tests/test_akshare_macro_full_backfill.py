from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.jobs import macro_job


class AkShareMacroFullBackfillTests(unittest.TestCase):
    def test_full_backfill_fetches_all_history_and_refreshes_cache(self) -> None:
        rows = [
            {"key": "AK_CHN_CPI_YOY:CHN", "date": date(2024, 1, 1), "value": 1.0, "score": 0.0},
            {"key": "AK_CHN_CPI_YOY:CHN", "date": date(2025, 1, 1), "value": 2.0, "score": 0.0},
        ]

        with patch.object(macro_job, "fetch_all_akshare_macro_rows", return_value=rows) as fetch_mock, patch.object(
            macro_job, "upsert_macro", return_value=2
        ) as upsert_mock, patch.object(
            macro_job, "_cache_latest_macro_rows", return_value=1
        ) as cache_mock, patch.object(
            macro_job, "update_job_state"
        ) as state_mock:
            total = macro_job.run_akshare_macro_full_backfill(end=date(2026, 6, 1))

        self.assertEqual(total, 2)
        fetch_mock.assert_called_once_with(start=None, end=date(2026, 6, 1))
        upsert_mock.assert_called_once_with(rows)
        cache_mock.assert_called_once()
        state_mock.assert_called_once_with(macro_job.MACRO_REFRESH_STATE_KEY, date(2026, 6, 1))


if __name__ == "__main__":
    unittest.main()
