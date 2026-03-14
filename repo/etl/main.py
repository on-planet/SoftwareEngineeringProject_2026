from __future__ import annotations

from datetime import date
from pathlib import Path

from etl.config.loader import load_config
from etl.scheduler import run_once
from etl.utils.console import install_console_shutdown
from etl.utils.dates import to_t1


def main(
    as_of: date | None = None,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    incremental: bool = True,
) -> None:
    """Run ETL pipeline for the given date (T-1 handled by config)."""

    install_console_shutdown(lambda: None)
    config = load_config(Path(__file__).parent / "config" / "settings.yml")
    target_date = to_t1(as_of or date.today(), config.t1_offset_days)
    run_once(
        as_of=target_date,
        start_date=start_date,
        end_date=end_date,
        incremental=incremental,
    )


if __name__ == "__main__":
    main()
