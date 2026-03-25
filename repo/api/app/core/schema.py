from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import engine


def _database_health_failure_message() -> str:
    return (
        "Database health check failed. Apply repo/db/init.sql for new databases "
        "and pending SQL files under repo/db/migrations before starting the API."
    )


def probe_database_connection() -> tuple[bool, str | None]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False, _database_health_failure_message()
    return True, None


def check_database_connection() -> None:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise RuntimeError(_database_health_failure_message()) from exc
