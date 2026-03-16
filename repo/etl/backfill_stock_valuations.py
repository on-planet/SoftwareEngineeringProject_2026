from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.jobs.sector_exposure_job import run_stock_valuation_backfill
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill stock valuation snapshots into stock_valuation_snapshots.")
    parser.add_argument("--start", required=True, help="Start date in YYYY-MM-DD format.")
    parser.add_argument("--end", required=True, help="End date in YYYY-MM-DD format.")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if start > end:
        raise SystemExit("start must be <= end")

    LOGGER.info("stock valuation backfill range=%s..%s", start, end)
    inserted = run_stock_valuation_backfill(start, end)
    print(inserted)


if __name__ == "__main__":
    main()
