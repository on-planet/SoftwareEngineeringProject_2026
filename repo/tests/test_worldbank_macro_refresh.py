from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.jobs import macro_job


@dataclass
class _State:
    last_success_date: date | None


class WorldBankMacroRefreshTests(unittest.TestCase):
    def test_macro_job_refreshes_world_bank_when_full_snapshot_incomplete(self) -> None:
        rows = [{"country": "USA", "indicator": "NY.GDP.MKTP.CD", "date": date(2025, 1, 1), "value": 1.0}]

        with patch.object(
            macro_job,
            "get_job_state",
            side_effect=[_State(date(2026, 3, 17)), _State(date(2026, 3, 17)), _State(date(2026, 3, 13))],
        ), patch.object(
            macro_job,
            "macro_snapshot_is_healthy",
            side_effect=lambda *args, **kwargs: False if kwargs.get("include_world_bank") else True,
        ), patch.object(
            macro_job, "fetch_all_akshare_macro_rows", return_value=[]
        ), patch.object(
            macro_job, "WORLD_BANK_COUNTRIES", ["USA"]
        ), patch.object(
            macro_job, "WORLD_BANK_INDICATORS", {"GDP": "NY.GDP.MKTP.CD"}
        ), patch.object(
            macro_job, "get_indicator_series", return_value=rows
        ) as fetch_mock, patch.object(
            macro_job, "normalize_macro_rows", return_value=[{"key": "GDP:USA", "date": date(2025, 1, 1), "value": 1.0, "score": 0.0}]
        ), patch.object(
            macro_job, "upsert_macro", return_value=1
        ), patch.object(
            macro_job, "_cache_latest_macro_rows", return_value=1
        ), patch.object(
            macro_job, "update_job_state"
        ) as update_mock:
            total = macro_job.run_macro_job(date(2026, 3, 17), date(2026, 3, 17))

        self.assertEqual(total, 1)
        fetch_mock.assert_called_once()
        update_mock.assert_called_once_with(macro_job.WORLD_BANK_REFRESH_STATE_KEY, date(2026, 3, 17))


if __name__ == "__main__":
    unittest.main()
