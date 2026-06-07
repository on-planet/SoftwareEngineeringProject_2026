from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.jobs.macro_job import run_akshare_macro_full_backfill


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill all historical AkShare macro rows.")
    parser.add_argument(
        "--end",
        type=str,
        default=date.today().isoformat(),
        help="Inclusive end date in YYYY-MM-DD. Defaults to today.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    total = run_akshare_macro_full_backfill(end=date.fromisoformat(args.end))
    print({"akshare_macro_rows": total, "end": args.end})


if __name__ == "__main__":
    main()
