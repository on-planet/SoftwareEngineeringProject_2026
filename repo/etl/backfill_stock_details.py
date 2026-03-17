from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.jobs.stock_detail_job import run_stock_detail_job


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill stock detail snapshots and research into local tables.")
    parser.add_argument("--symbols", help="Comma separated symbols", default="")
    parser.add_argument("--markets", help="Comma separated markets, default A,HK", default="A,HK")
    parser.add_argument("--limit", type=int, default=0, help="Max symbols to crawl when symbols are not specified, 0 means all")
    parser.add_argument("--report-limit", type=int, default=10)
    parser.add_argument("--forecast-limit", type=int, default=10)
    parser.add_argument("--no-resume", action="store_true", help="Do not resume from the last checkpoint")
    parser.add_argument("--reset-progress", action="store_true", help="Clear the saved checkpoint before crawling")
    parser.add_argument("--force-refresh", action="store_true", help="Refresh all matched symbols even if local data is fresh")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    symbols = [item.strip() for item in args.symbols.split(",") if item.strip()] or None
    markets = [item.strip().upper() for item in args.markets.split(",") if item.strip()] or None
    snapshot_count, research_count = run_stock_detail_job(
        symbols=symbols,
        markets=markets,
        limit=args.limit if args.limit > 0 else None,
        report_limit=args.report_limit,
        forecast_limit=args.forecast_limit,
        resume=not args.no_resume,
        reset_progress=args.reset_progress,
        force_refresh=args.force_refresh,
    )
    print(f"snapshots={snapshot_count} research={research_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
