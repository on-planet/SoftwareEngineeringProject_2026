from __future__ import annotations

import argparse
from datetime import datetime, time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.loaders.pg_loader import list_news_rows, update_news_sentiment
from etl.utils.news_sentiment import infer_news_sentiment


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill sentiment field from existing news titles.")
    parser.add_argument("--start", help="Start date in YYYY-MM-DD", default=None)
    parser.add_argument("--end", help="End date in YYYY-MM-DD", default=None)
    parser.add_argument("--limit", type=int, default=2000, help="Max rows to process per run")
    parser.add_argument("--offset", type=int, default=0, help="Offset rows for batch processing")
    parser.add_argument("--dry-run", action="store_true", help="Only count update candidates without writing")
    return parser.parse_args()


def _to_range(value: str | None, *, end: bool) -> datetime | None:
    if not value:
        return None
    parsed = datetime.strptime(value, "%Y-%m-%d")
    return datetime.combine(parsed.date(), time.max if end else time.min)


def main() -> int:
    args = _parse_args()
    start = _to_range(args.start, end=False)
    end = _to_range(args.end, end=True)
    rows = list_news_rows(start=start, end=end, limit=args.limit, offset=args.offset)

    updates: list[dict] = []
    for row in rows:
        sentiment = infer_news_sentiment(
            str(row.get("title") or ""),
            source=str(row.get("source") or ""),
            topic_category=str(row.get("topic_category") or ""),
        )
        if sentiment == str(row.get("sentiment") or ""):
            continue
        updates.append(
            {
                "id": row.get("id"),
                "sentiment": sentiment,
            }
        )

    if args.dry_run:
        print(len(updates))
        return 0

    written = update_news_sentiment(updates)
    print(written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
