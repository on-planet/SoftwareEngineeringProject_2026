from __future__ import annotations

import argparse
from datetime import datetime, time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.loaders.pg_loader import list_news_rows, update_news_metadata
from etl.utils.news_nlp import extract_news_nlp
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
        sentiment = str(row.get("sentiment") or "")
        nlp = extract_news_nlp(
            str(row.get("title") or ""),
            symbol=str(row.get("symbol") or ""),
            source=row.get("source"),
            topic_category=metadata.get("topic_category"),
            sentiment=sentiment,
        )
        candidate = {
            "id": row.get("id"),
            "source_site": metadata.get("source_site"),
            "source_category": metadata.get("source_category"),
            "topic_category": metadata.get("topic_category"),
            "time_bucket": metadata.get("time_bucket"),
            "related_symbols": nlp.related_symbols,
            "related_sectors": nlp.related_sectors,
            "event_type": nlp.event_type,
            "event_tags": nlp.event_tags,
            "themes": nlp.themes,
            "impact_direction": nlp.impact_direction,
            "nlp_confidence": nlp.confidence,
            "nlp_version": nlp.version,
            "keywords": nlp.keywords,
        }
        if (
            candidate["source_site"] == row.get("source_site")
            and candidate["source_category"] == row.get("source_category")
            and candidate["topic_category"] == row.get("topic_category")
            and candidate["time_bucket"] == row.get("time_bucket")
            and ",".join(candidate["related_symbols"] or []) == str(row.get("related_symbols") or "")
            and ",".join(candidate["related_sectors"] or []) == str(row.get("related_sectors") or "")
            and candidate["event_type"] == row.get("event_type")
            and ",".join(candidate["event_tags"] or []) == str(row.get("event_tags") or "")
            and ",".join(candidate["themes"] or []) == str(row.get("themes") or "")
            and candidate["impact_direction"] == row.get("impact_direction")
            and float(candidate["nlp_confidence"] or 0) == float(row.get("nlp_confidence") or 0)
            and candidate["nlp_version"] == row.get("nlp_version")
            and ",".join(candidate["keywords"] or []) == str(row.get("keywords") or "")
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
