from __future__ import annotations

import argparse
from datetime import date

from app.core.db import SessionLocal
from app.tasks.refresh_cache import rebuild_macro_cache


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild macro Redis cache from database.")
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="Optional cutoff date in YYYY-MM-DD format.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    db = SessionLocal()
    try:
        count = rebuild_macro_cache(db, as_of=args.as_of)
    finally:
        db.close()
    print(f"rebuilt macro cache items: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
