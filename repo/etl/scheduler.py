from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Callable

from sqlalchemy.orm import Session

from etl.config.loader import load_config
from etl.jobs.events_job import run_events_job
from etl.jobs.financial_job import run_financial_job
from etl.jobs.futures_job import run_futures_job
from etl.jobs.index_job import run_index_job
from etl.jobs.macro_job import macro_snapshot_is_healthy, run_macro_job
from etl.jobs.news_job import run_news_job
from etl.jobs.index_constituent_job import run_index_constituent_job
from etl.jobs.sector_exposure_job import run_sector_exposure_job
from etl.jobs.fund_holdings_job import run_fund_holdings_job
from etl.jobs.cache_metrics_job import (
    list_updated_symbols,
    run_metrics_cache_job,
)
from etl.loaders.pg_loader import (
    delete_events_before,
    delete_index_constituents_before,
    delete_news_before,
    delete_buyback_before,
    delete_insider_trade_before,
)
from etl.utils.console import install_console_shutdown
from etl.utils.dates import to_t1
from etl.utils.logging import get_logger
from etl.utils.alerting import notify_error, notify_batch
from etl.utils.state import get_job_state, update_job_state
from etl.utils.db_pool import create_session

LOGGER = get_logger(__name__)
LOCK_PATH = Path(__file__).resolve().parents[1] / "state" / "etl.lock"
DEFAULT_RETENTION_DAYS = 7
DEFAULT_NEWS_EVENT_RETENTION_DAYS = 30


@dataclass
class JobConfig:
    name: str
    at: str
    runner: Callable[[date, date], int]
    stage: str = "core"


@dataclass
class PlannedJob:
    config: JobConfig
    start: date
    end: date


def _get_db_session(
    database_url: str | None,
    *,
    pool_size: int = 5,
    max_overflow: int = 5,
    pool_timeout: int = 30,
    pool_recycle: int = 1800,
) -> Session:
    """
    创建数据库 Session，使用共享的连接池。
    
    Args:
        database_url: 数据库连接字符串
        pool_size: 连接池大小
        max_overflow: 最大溢出连接数
        pool_timeout: 连接超时时间（秒）
        pool_recycle: 连接回收时间（秒）
    
    Returns:
        Session: SQLAlchemy Session 实例
    """
    if not database_url:
        raise ValueError("postgres_url 未配置")
    
    return create_session(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
    )


def _parse_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _is_process_running(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
    except OSError:
        return False
    return True


def _acquire_lock() -> bool:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists():
        try:
            payload = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        except Exception:
            payload = {}
        pid = payload.get("pid")
        if pid and _is_process_running(pid):
            LOGGER.warning("ETL 已在运行中（锁文件存在且进程存活），跳过本次执行")
            return False
        # 进程不存在或 pid 缺失时，认为是陈旧锁，清理后继续
        try:
            LOCK_PATH.unlink()
        except Exception:
            pass
    try:
        LOCK_PATH.write_text(
            json.dumps(
                {"pid": os.getpid(), "ts": datetime.now(timezone.utc).timestamp()},
                ensure_ascii=False,
            ),
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


def _should_skip_job(
    job_name: str,
    job_end: date,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    incremental: bool = True,
    force: bool = False,
) -> bool:
    if force:
        return False
    if start_date is not None or end_date is not None:
        return False
    if not incremental:
        return False
    if job_name == "macro_job" and not macro_snapshot_is_healthy(include_world_bank=True):
        return False
    state = get_job_state(job_name)
    return state.last_success_date is not None and state.last_success_date >= job_end


def _cleanup_retention(
    target_date: date,
    *,
    news_event_days: int = DEFAULT_NEWS_EVENT_RETENTION_DAYS,
    retention_days: int = DEFAULT_RETENTION_DAYS,
) -> None:
    news_event_cutoff = target_date - timedelta(days=news_event_days - 1)
    general_cutoff = target_date - timedelta(days=retention_days - 1)
    delete_news_before(news_event_cutoff)
    delete_events_before(news_event_cutoff)
    delete_buyback_before(general_cutoff)
    delete_insider_trade_before(general_cutoff)
    delete_index_constituents_before(general_cutoff)


def _plan_jobs(
    jobs: list[JobConfig],
    target_date: date,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    incremental: bool = True,
    force: bool = False,
    lookback_days: int = 0,
) -> list[PlannedJob]:
    planned: list[PlannedJob] = []
    for job in jobs:
        job_start, job_end = _resolve_range(
            job.name,
            target_date,
            start_date=start_date,
            end_date=end_date,
            incremental=incremental,
            lookback_days=lookback_days,
        )
        if job.name in {"macro_job", "news_job", "events_job", "index_constituent_job", "sector_exposure_job"}:
            job_start = target_date
            job_end = target_date
        if _should_skip_job(
            job.name,
            job_end,
            start_date=start_date,
            end_date=end_date,
            incremental=incremental,
            force=force,
        ):
            LOGGER.info("Skipping %s because last_success_date already covers %s", job.name, job_end)
            continue
        planned.append(PlannedJob(config=job, start=job_start, end=job_end))
    return planned


def _run_planned_job(job: PlannedJob) -> tuple[str, int]:
    LOGGER.info("Running %s [%s -> %s]", job.config.name, job.start, job.end)
    result = job.config.runner(job.start, job.end)
    if job.config.name == "macro_job" and not macro_snapshot_is_healthy(include_world_bank=True):
        LOGGER.warning("macro_job completed but full macro snapshot is still incomplete")
    update_job_state(job.config.name, job.end)
    return job.config.name, int(result or 0)


def _run_job_stage(stage_name: str, jobs: list[PlannedJob], *, max_workers: int) -> tuple[list[str], bool]:
    if not jobs:
        return [], False
    errors: list[str] = []
    any_job_ran = False
    worker_count = max(1, min(max_workers, len(jobs)))
    LOGGER.info("Running ETL stage %s with workers=%s jobs=%s", stage_name, worker_count, len(jobs))
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix=f"etl_{stage_name}") as executor:
        future_map = {executor.submit(_run_planned_job, job): job for job in jobs}
        for future in as_completed(future_map):
            job = future_map[future]
            try:
                job_name, row_count = future.result()
                LOGGER.info("Completed %s rows=%s", job_name, row_count)
                any_job_ran = True
            except Exception as exc:
                LOGGER.exception("Job failed: %s", job.config.name, exc_info=exc)
                errors.append(f"{job.config.name}: {exc}")
                notify_error(job.config.name, str(exc))
    return errors, any_job_ran


def run_once(
    as_of: date | None = None,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    incremental: bool = True,
    force: bool = False,
) -> None:
    install_console_shutdown(lambda: None)
    force = force or os.getenv("ETL_FORCE_RUN", "0").lower() in {"1", "true", "yes"}
    if not _acquire_lock():
        return
    try:
        config = load_config(Path(__file__).parent / "config" / "settings.yml")
        
        # 优化：根据并行工作线程数动态调整连接池大小
        parallel_workers = max(1, int(config.raw.get("etl", {}).get("parallel_workers", 4)))
        pool_size = max(parallel_workers + 2, config.postgres_pool_size)
        max_overflow = max(parallel_workers, config.postgres_max_overflow)
        
        db_session = _get_db_session(
            config.postgres_url,
            pool_size=pool_size,
            max_overflow=max_overflow,
        )
        try:
            target_date = to_t1(as_of or date.today(), config.t1_offset_days)
            lookback_days = int(config.raw.get("etl", {}).get("incremental_lookback_days", 0))
            retention_days = max(1, int(config.raw.get("etl", {}).get("retention_days", DEFAULT_RETENTION_DAYS)))
            news_event_retention_days = max(
                1,
                int(config.raw.get("etl", {}).get("news_event_retention_days", DEFAULT_NEWS_EVENT_RETENTION_DAYS)),
            )
            parallel_workers = max(1, int(config.raw.get("etl", {}).get("parallel_workers", 4)))
            jobs = [
                JobConfig("index_job", config.raw.get("etl", {}).get("schedules", {}).get("index_job", "00:30"), run_index_job, stage="source"),
                JobConfig("financial_job", config.raw.get("etl", {}).get("schedules", {}).get("financial_job", "01:00"), run_financial_job, stage="source"),
                JobConfig("news_job", config.raw.get("etl", {}).get("schedules", {}).get("news_job", "01:30"), run_news_job, stage="source"),
                JobConfig("macro_job", config.raw.get("etl", {}).get("schedules", {}).get("macro_job", "02:00"), run_macro_job, stage="source"),
                JobConfig("events_job", config.raw.get("etl", {}).get("schedules", {}).get("events_job", "02:30"), run_events_job, stage="source"),
                JobConfig("index_constituent_job", config.raw.get("etl", {}).get("schedules", {}).get("index_constituent_job", "03:00"), run_index_constituent_job, stage="source"),
                JobConfig("fund_holdings_job", config.raw.get("etl", {}).get("schedules", {}).get("fund_holdings_job", "04:00"), run_fund_holdings_job, stage="source"),
                JobConfig("futures_job", config.raw.get("etl", {}).get("schedules", {}).get("futures_job", "04:30"), run_futures_job, stage="source"),
                JobConfig("sector_exposure_job", config.raw.get("etl", {}).get("schedules", {}).get("sector_exposure_job", "03:30"), run_sector_exposure_job, stage="derived"),
            ]
            planned_jobs = _plan_jobs(
                jobs,
                target_date,
                start_date=start_date,
                end_date=end_date,
                incremental=incremental,
                force=force,
                lookback_days=lookback_days,
            )
            stage_order = ("source", "derived", "background")
            errors: list[str] = []
            any_job_ran = False
            for stage_name in stage_order:
                stage_jobs = [job for job in planned_jobs if job.config.stage == stage_name]
                stage_errors, stage_ran = _run_job_stage(stage_name, stage_jobs, max_workers=parallel_workers)
                errors.extend(stage_errors)
                any_job_ran = any_job_ran or stage_ran
            if errors:
                notify_batch(errors)
            _cleanup_retention(
                target_date,
                news_event_days=news_event_retention_days,
                retention_days=retention_days,
            )
            try:
                metrics_target_date = end_date or target_date
                if any_job_ran or not _should_skip_job(
                    "metrics_cache_job",
                    metrics_target_date,
                    start_date=start_date,
                    end_date=end_date,
                    incremental=incremental,
                    force=force,
                ):
                    symbols = list_updated_symbols(db_session, metrics_target_date)
                    if not symbols:
                        LOGGER.info("Skipping metrics_cache_job because no changed symbols were found on %s", metrics_target_date)
                    else:
                        processed = run_metrics_cache_job(
                            config.postgres_url,
                            symbols,
                            end=metrics_target_date,
                        )
                        LOGGER.info(
                            "metrics_cache_job processed %s/%s symbols on %s",
                            processed,
                            len(symbols),
                            metrics_target_date,
                        )
                    update_job_state("metrics_cache_job", metrics_target_date)
                else:
                    LOGGER.info("Skipping metrics_cache_job because last_success_date already covers %s", metrics_target_date)
            except Exception as exc:
                LOGGER.exception("metrics_cache failed: %s", exc, exc_info=exc)
                notify_error("metrics_cache", str(exc))
        finally:
            db_session.close()
    finally:
        _release_lock()
        # 注意：不在这里 dispose 引擎，因为可能有其他地方在使用
        # 引擎会在进程结束时自动清理


if __name__ == "__main__":
    run_once()
