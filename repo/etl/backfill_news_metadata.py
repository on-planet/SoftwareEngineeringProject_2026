from __future__ import annotations

import argparse
from datetime import datetime, time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.loaders.pg_loader import list_news_rows, update_news_metadata
from etl.utils.news_relevance import infer_news_relevance
from etl.utils.news_taxonomy import classify_news_metadata


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill news metadata fields from existing news rows.")
    parser.add_argument("--start", help="Start date in YYYY-MM-DD", default=None)
    parser.add_argument("--end", help="End date in YYYY-MM-DD", default=None)
    parser.add_argument("--limit", type=int, default=1000, help="Max rows to process per run")
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
        metadata = classify_news_metadata(
            source=row.get("source"),
            link=row.get("link"),
            published_at=row.get("published_at"),
        )
        relevance = infer_news_relevance(
            str(row.get("title") or ""),
            symbol=str(row.get("symbol") or ""),
        )
        candidate = {
            "id": row.get("id"),
            "source_site": metadata.get("source_site"),
            "source_category": metadata.get("source_category"),
            "topic_category": metadata.get("topic_category"),
            "time_bucket": metadata.get("time_bucket"),
            "related_symbols": relevance.get("related_symbols"),
            "related_sectors": relevance.get("related_sectors"),
        }
        if (
            candidate["source_site"] == row.get("source_site")
            and candidate["source_category"] == row.get("source_category")
            and candidate["topic_category"] == row.get("topic_category")
            and candidate["time_bucket"] == row.get("time_bucket")
            and candidate["related_symbols"] == row.get("related_symbols")
            and candidate["related_sectors"] == row.get("related_sectors")
        ):
            continue
        updates.append(candidate)
    if args.dry_run:
        print(len(updates))
        return 0
    written = update_news_metadata(updates)
    print(written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
