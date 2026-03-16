from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.jobs.futures_job import run_futures_job, run_futures_weekly_job, weekly_snapshot_dates
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill SHFE weekly futures snapshots into futures_weekly_prices.")
    parser.add_argument("--start", required=True, help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end", required=True, help="End date in YYYY-MM-DD format.")
    parser.add_argument(
        "--include-daily",
        action="store_true",
        help="Also backfill daily futures rows for the same range.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if start > end:
        raise SystemExit("start must be <= end")

    weekly_dates = weekly_snapshot_dates(start, end)
    LOGGER.info("weekly futures backfill range=%s..%s snapshots=%s", start, end, len(weekly_dates))

    if args.include_daily:
        inserted = run_futures_job(start, end)
        print(inserted)
        return

    inserted = run_futures_weekly_job(start, end)
    print(inserted)


if __name__ == "__main__":
    main()
