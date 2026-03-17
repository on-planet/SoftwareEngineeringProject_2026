from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from etl.jobs.macro_job import run_macro_job
from etl.jobs.news_job import run_news_job
from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill macro and news jobs in parallel.")
    parser.add_argument("--macro-start", type=str, default="2024-01-01", help="Macro start date in YYYY-MM-DD.")
    parser.add_argument("--news-start", type=str, default="2026-03-01", help="News start date in YYYY-MM-DD.")
    parser.add_argument(
        "--worldbank-start",
        type=str,
        default="2024-01-01",
        help="Deprecated. World Bank refresh is now merged into macro_job.",
    )
    parser.add_argument("--skip-macro", action="store_true", help="Skip AkShare macro refresh.")
    parser.add_argument("--skip-news", action="store_true", help="Skip news refresh.")
    parser.add_argument(
        "--include-worldbank",
        action="store_true",
        help="Deprecated. World Bank refresh is now merged into macro_job.",
    )
    return parser.parse_args()


def run_backfill(
    *,
    macro_start: date,
    news_start: date,
    worldbank_start: date,
    include_worldbank: bool = False,
    skip_macro: bool = False,
    skip_news: bool = False,
) -> dict[str, int]:
    today = date.today()
    tasks: list[tuple[str, callable]] = []
    _ = worldbank_start
    if include_worldbank:
        LOGGER.info("backfill option --include-worldbank is deprecated; macro_job now includes world bank refresh")
    if not skip_macro:
        tasks.append(("macro", lambda: run_macro_job(macro_start, today)))
    if not skip_news:
        tasks.append(("news", lambda: run_news_job(news_start, today)))

    if not tasks:
        LOGGER.info("macro/news backfill skipped: no jobs selected")
        return {}

    results: dict[str, int] = {}
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        future_map = {executor.submit(task): name for name, task in tasks}
        for future in as_completed(future_map):
            name = future_map[future]
            results[name] = int(future.result())
            LOGGER.info("macro/news backfill completed job=%s rows=%s", name, results[name])

    return results


def main() -> None:
    args = _parse_args()
    results = run_backfill(
        macro_start=date.fromisoformat(args.macro_start),
        news_start=date.fromisoformat(args.news_start),
        worldbank_start=date.fromisoformat(args.worldbank_start),
        include_worldbank=args.include_worldbank,
        skip_macro=args.skip_macro,
        skip_news=args.skip_news,
    )
    print(results)


if __name__ == "__main__":
    main()
