from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict

from etl.utils.logging import get_logger

LOGGER = get_logger(__name__)
STATE_DIR = Path(__file__).resolve().parents[1] / "state"
STATE_PATH = STATE_DIR / "etl_state.json"


@dataclass
class JobState:
    last_success_date: date | None


def _ensure_state_file() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_PATH.exists():
        STATE_PATH.write_text("{}", encoding="utf-8")


def _load_state() -> Dict[str, Any]:
    _ensure_state_file()
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            return raw
    except json.JSONDecodeError:
        LOGGER.warning("ETL state 文件损坏，已重置: %s", STATE_PATH)
    return {}


def _save_state(state: Dict[str, Any]) -> None:
    _ensure_state_file()
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def get_job_state(job_name: str) -> JobState:
    state = _load_state()
    value = state.get(job_name, {})
    last_date = value.get("last_success_date") if isinstance(value, dict) else None
    if last_date:
        try:
            parsed = date.fromisoformat(last_date)
        except ValueError:
            parsed = None
    else:
        parsed = None
    return JobState(last_success_date=parsed)


def update_job_state(job_name: str, last_success_date: date) -> None:
    state = _load_state()
    state[job_name] = {"last_success_date": last_success_date.isoformat()}
    _save_state(state)
