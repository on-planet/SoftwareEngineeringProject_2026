from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.jobs.futures_job import weekly_snapshot_dates


class FuturesBackfillScriptTests(unittest.TestCase):
    def test_weekly_snapshot_dates_collapses_range_to_unique_fridays(self) -> None:
        dates = weekly_snapshot_dates(date(2026, 3, 9), date(2026, 3, 22))
        self.assertEqual(dates, [date(2026, 3, 13), date(2026, 3, 20)])


if __name__ == "__main__":
    unittest.main()
