from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
import json
import os
from pathlib import Path
from typing import Callable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from etl.config.loader import load_config
from etl.jobs.events_job import run_events_job
from etl.jobs.financial_job import run_financial_job
from etl.jobs.index_job import run_index_job
from etl.jobs.macro_job import run_macro_job
from etl.jobs.news_job import run_news_job
from etl.jobs.index_constituent_job import run_index_constituent_job
from etl.jobs.sector_exposure_job import run_sector_exposure_job
from etl.jobs.fund_holdings_job import run_fund_holdings_job
from etl.jobs.cache_metrics_job import write_risk_series_cache, write_indicator_cache, list_symbols
from etl.utils.dates import to_t1
from etl.utils.logging import get_logger
from etl.utils.alerting import notify_error, notify_batch
from etl.utils.state import get_job_state, update_job_state

LOGGER = get_logger(__name__)
LOCK_PATH = Path(__file__).resolve().parents[1] / "state" / "etl.lock"


@dataclass
class JobConfig:
    name: str
    at: str
    runner: Callable[[date, date], int]


def _get_db_session(database_url: str | None) -> Session:
    if not database_url:
        raise ValueError("postgres_url 未配置")
    engine = create_engine(database_url, pool_pre_ping=True)
    return Session(bind=engine)


def _parse_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _acquire_lock() -> bool:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists():
        try:
            payload = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        ts = payload.get("ts", 0)
        if isinstance(ts, (int, float)):
            age = datetime.utcnow().timestamp() - ts
            if age < 6 * 3600:
                LOGGER.warning("ETL 已在运行中（锁文件存在），跳过本次执行")
                return False
    try:
        LOCK_PATH.write_text(
            json.dumps({"pid": os.getpid(), "ts": datetime.utcnow().timestamp()}, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        return True
    return True


def _release_lock() -> None:
    try:
        if LOCK_PATH.exists():
            LOCK_PATH.unlink()
    except Exception:
        return


def _resolve_range(
    job_name: str,
    target_date: date,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    incremental: bool = True,
    lookback_days: int = 0,
) -> tuple[date, date]:
    if start_date and end_date:
        return start_date, end_date
    if start_date and not end_date:
        return start_date, target_date
    if not incremental:
        return target_date, target_date

    # 默认仅抓取 T-1（不补历史区间）
    return target_date, target_date


def run_once(
    as_of: date | None = None,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    incremental: bool = True,
) -> None:
    if not _acquire_lock():
        return
    try:
        config = load_config(Path(__file__).parent / "config" / "settings.yml")
        db_session = _get_db_session(config.postgres_url)
        target_date = to_t1(as_of or date.today(), config.t1_offset_days)
        lookback_days = int(config.raw.get("etl", {}).get("incremental_lookback_days", 0))
        jobs = [
            JobConfig("index_job", config.raw.get("etl", {}).get("schedules", {}).get("index_job", "00:30"), run_index_job),
            JobConfig("financial_job", config.raw.get("etl", {}).get("schedules", {}).get("financial_job", "01:00"), run_financial_job),
            JobConfig("news_job", config.raw.get("etl", {}).get("schedules", {}).get("news_job", "01:30"), run_news_job),
            JobConfig("macro_job", config.raw.get("etl", {}).get("schedules", {}).get("macro_job", "02:00"), run_macro_job),
            JobConfig("events_job", config.raw.get("etl", {}).get("schedules", {}).get("events_job", "02:30"), run_events_job),
            JobConfig("index_constituent_job", config.raw.get("etl", {}).get("schedules", {}).get("index_constituent_job", "03:00"), run_index_constituent_job),
            JobConfig("sector_exposure_job", config.raw.get("etl", {}).get("schedules", {}).get("sector_exposure_job", "03:30"), run_sector_exposure_job),
            JobConfig("fund_holdings_job", config.raw.get("etl", {}).get("schedules", {}).get("fund_holdings_job", "04:00"), run_fund_holdings_job),
        ]
        errors = []
        for job in jobs:
            try:
                LOGGER.info("Running %s", job.name)
                job_start, job_end = _resolve_range(
                    job.name,
                    target_date,
                    start_date=start_date,
                    end_date=end_date,
                    incremental=incremental,
                    lookback_days=lookback_days,
                )
                job.runner(job_start, job_end)
                update_job_state(job.name, job_end)
            except Exception as exc:
                LOGGER.exception("Job failed: %s", job.name, exc_info=exc)
                errors.append(f"{job.name}: {exc}")
                notify_error(job.name, str(exc))
        if errors:
            notify_batch(errors)
        try:
            metric_limit = int(config.raw.get("etl", {}).get("metrics_cache_limit", 200))
            symbols = list_symbols(db_session, limit=metric_limit)
            for symbol in symbols:
                write_risk_series_cache(db_session, symbol)
                write_indicator_cache(db_session, symbol, "ma", window=20)
                write_indicator_cache(db_session, symbol, "rsi", window=14)
        except Exception as exc:
            LOGGER.exception("metrics_cache failed: %s", exc, exc_info=exc)
            notify_error("metrics_cache", str(exc))
    finally:
        _release_lock()


if __name__ == "__main__":
    run_once()
