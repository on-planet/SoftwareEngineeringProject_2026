from __future__ import annotations

from datetime import date
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "api") not in sys.path:
    sys.path.insert(0, str(ROOT / "api"))

if "pydantic_settings" not in sys.modules:
    fake_module = types.ModuleType("pydantic_settings")

    class BaseSettings:  # pragma: no cover - import shim for tests
        def __init__(self, **kwargs):
            annotations: dict[str, object] = {}
            for cls in reversed(self.__class__.mro()):
                annotations.update(getattr(cls, "__annotations__", {}))
            for key in annotations:
                if key in kwargs:
                    value = kwargs[key]
                else:
                    value = getattr(self.__class__, key, None)
                setattr(self, key, value)

    fake_module.BaseSettings = BaseSettings
    sys.modules["pydantic_settings"] = fake_module

from etl import scheduler


class SchedulerParallelTests(unittest.TestCase):
    def test_cleanup_retention_does_not_delete_macro_rows(self) -> None:
        with (
            patch.object(scheduler, "delete_news_before") as delete_news_mock,
            patch.object(scheduler, "delete_events_before") as delete_events_mock,
            patch.object(scheduler, "delete_buyback_before") as delete_buyback_mock,
            patch.object(scheduler, "delete_insider_trade_before") as delete_insider_trade_mock,
            patch.object(scheduler, "delete_index_constituents_before") as delete_index_constituents_mock,
        ):
            scheduler._cleanup_retention(date(2026, 3, 16), days=7)

        delete_news_mock.assert_called_once_with(date(2026, 3, 10))
        delete_events_mock.assert_called_once_with(date(2026, 3, 10))
        delete_buyback_mock.assert_called_once_with(date(2026, 3, 10))
        delete_insider_trade_mock.assert_called_once_with(date(2026, 3, 10))
        delete_index_constituents_mock.assert_called_once_with(date(2026, 3, 10))

    def test_run_once_only_schedules_macro_job_for_macro_refresh(self) -> None:
        recorded: list[tuple[str, list[str]]] = []

        class _FakeSession:
            def close(self):
                return None

        class _FakeConfig:
            postgres_url = "postgresql://example"
            raw = {
                "etl": {
                    "parallel_workers": 2,
                    "incremental_lookback_days": 0,
                    "schedules": {},
                }
            }
            t1_offset_days = 1

        def fake_run_job_stage(stage_name: str, jobs: list[scheduler.PlannedJob], *, max_workers: int):
            recorded.append((stage_name, [job.config.name for job in jobs]))
            return [], False

        with (
            patch.object(scheduler, "_acquire_lock", return_value=True),
            patch.object(scheduler, "_release_lock"),
            patch.object(scheduler, "install_console_shutdown"),
            patch.object(scheduler, "load_config", return_value=_FakeConfig()),
            patch.object(scheduler, "_get_db_session", return_value=_FakeSession()),
            patch.object(scheduler, "to_t1", return_value=date(2026, 3, 16)),
            patch.object(scheduler, "_should_skip_job", return_value=False),
            patch.object(scheduler, "_run_job_stage", side_effect=fake_run_job_stage),
            patch.object(scheduler, "_cleanup_retention"),
            patch.object(scheduler, "list_updated_symbols", return_value=[]),
        ):
            scheduler.run_once(as_of=date(2026, 3, 17))

        source_jobs = next(names for stage, names in recorded if stage == "source")
        background_jobs = next(names for stage, names in recorded if stage == "background")
        self.assertIn("macro_job", source_jobs)
        self.assertNotIn("worldbank_macro_job", source_jobs)
        self.assertNotIn("worldbank_macro_job", background_jobs)

    def test_should_not_skip_macro_job_when_full_snapshot_incomplete(self) -> None:
        with (
            patch.object(scheduler, "get_job_state") as state_mock,
            patch.object(
                scheduler,
                "macro_snapshot_is_healthy",
                return_value=False,
            ),
        ):
            state_mock.return_value.last_success_date = date(2026, 3, 16)
            should_skip = scheduler._should_skip_job("macro_job", date(2026, 3, 16))

        self.assertFalse(should_skip)

    def test_run_job_stage_processes_multiple_jobs_and_updates_state(self) -> None:
        calls: list[str] = []

        def make_runner(name: str):
            def _runner(start: date, end: date) -> int:
                calls.append(f"{name}:{start.isoformat()}:{end.isoformat()}")
                return 1

            return _runner

        jobs = [
            scheduler.PlannedJob(scheduler.JobConfig("news_job", "01:30", make_runner("news_job"), stage="source"), date(2026, 3, 16), date(2026, 3, 16)),
            scheduler.PlannedJob(scheduler.JobConfig("macro_job", "02:00", make_runner("macro_job"), stage="source"), date(2026, 3, 16), date(2026, 3, 16)),
        ]

        with (
            patch.object(scheduler, "update_job_state") as update_state_mock,
            patch.object(scheduler, "macro_snapshot_is_healthy", return_value=True),
            patch.object(scheduler, "notify_error") as notify_error_mock,
        ):
            errors, any_job_ran = scheduler._run_job_stage("source", jobs, max_workers=2)

        self.assertEqual(errors, [])
        self.assertTrue(any_job_ran)
        self.assertEqual(len(calls), 2)
        self.assertEqual(update_state_mock.call_count, 2)
        notify_error_mock.assert_not_called()

    def test_run_job_stage_keeps_other_jobs_running_when_one_fails(self) -> None:
        def ok_runner(start: date, end: date) -> int:
            return 2

        def bad_runner(start: date, end: date) -> int:
            raise RuntimeError("boom")

        jobs = [
            scheduler.PlannedJob(scheduler.JobConfig("news_job", "01:30", ok_runner, stage="source"), date(2026, 3, 16), date(2026, 3, 16)),
            scheduler.PlannedJob(scheduler.JobConfig("events_job", "02:30", bad_runner, stage="source"), date(2026, 3, 16), date(2026, 3, 16)),
        ]

        with (
            patch.object(scheduler, "update_job_state") as update_state_mock,
            patch.object(scheduler, "macro_snapshot_is_healthy", return_value=True),
            patch.object(scheduler, "notify_error") as notify_error_mock,
        ):
            errors, any_job_ran = scheduler._run_job_stage("source", jobs, max_workers=2)

        self.assertTrue(any_job_ran)
        self.assertEqual(len(errors), 1)
        self.assertIn("events_job", errors[0])
        self.assertEqual(update_state_mock.call_count, 1)
        notify_error_mock.assert_called_once()


if __name__ == "__main__":
    unittest.main()
